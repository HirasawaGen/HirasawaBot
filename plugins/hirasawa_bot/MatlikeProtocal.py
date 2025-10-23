from __future__ import annotations
from typing import Protocol
from typing import Sized, Iterable, Any, Callable
from typing import runtime_checkable

from functools import wraps

import ast


@runtime_checkable
class TensorProtocol( Protocol, Sized, Iterable):
    '''
    protocol of numpy.typing.NDArray and torch.tensor etc.
    '''
    @property
    def shape(self) -> tuple[int, ...]: ...
    
    @property
    def ndim(self) -> int: ...

def _safe_eval(expr, globals: dict | None = None, locals: dict | None = None) -> Any:
    # 解析表达式为语法树
    try:
        tree = ast.parse(expr, mode='eval')
    except SyntaxError:
        raise ValueError("Invalid expression syntax")
    
    # 检查所有节点是否合法（只允许操作符和字面量）
    allowed_nodes = (
        ast.Name,        # 变量名
        ast.Load,        # 变量加载
        ast.Expression,  # 根节点
        ast.BinOp,       # 二元操作符（+、-、*等）
        ast.UnaryOp,     # 一元操作符（-、+等）
        ast.Constant,    # 字面量（数字、字符串等，Python 3.8+）
        ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod,  # 二元操作符类型
    )
    
    for node in ast.walk(tree):
        if not isinstance(node, allowed_nodes):
            raise ValueError(f"Invalid element in expression: {type(node).__name__}")
    
    # 安全执行合法表达式
    return eval(compile(tree, '<string>', 'eval'), globals, locals)


def _parse_str(expr: str, mapping: dict, actual_size: int) -> int:
    if expr.isdigit():
        return int(expr)
    elif expr.isidentifier():
        if expr not in mapping:
            mapping[expr] = actual_size
        return mapping[expr]
    else:
        try:
            return int(_safe_eval(expr, {}, mapping))
        except NameError:
            # mat_1 = TensorValidator['a', 'a+1']  # right
            # mat_2 = TensorValidator['b+1', 'b']  # error
            raise ValueError(f'String size must be a single string when they first used.')
        except TypeError:
            # mat = TensorValidator['a', 'a+1.23']   # error
            raise ValueError(f'Expression must return an integer.')
        except SyntaxError:
            # mat = TensorValidator['a', 3, 4:7, 'a++']  # error
            raise ValueError(f'Invalid size expression: {expr}')
        except Exception as e:
            # I don't what other exception can be raised here.
            print(e)
            raise ValueError(f'Invalid size expression: {expr}')


class _TensorValidator:
    def __init__(self, size: tuple[int | slice | str, ...]):
        '''
        int is regular constant size
        slice[int, int] is range
        str is special mark or expression.
        when str is 'a', 'a' will be set to owner.__size_mapping__ as key.
        the value of 'a' is the corresponding size of the tensor.
        slice ':' or string '*' means any size.
        '''
        self._size = size
    
    def __set_name__(self, owner, name):
        self._name = name
        self._private_name = '_' + name
        
    def __get__(self, owner, objtype=None) -> TensorProtocol:
        return getattr(owner, self._private_name)
    
    def __set__(self, owner, value: TensorProtocol):
        if not hasattr(owner, '__size_mapping__'):
            owner.__size_mapping__ = {}
        mapping = owner.__size_mapping__
        self(mapping, value)
        setattr(owner, self._private_name, value)

    def __call__(self, mapping, value: Any) -> None:
        if not isinstance(value, TensorProtocol):
            raise TypeError(f'{self._name} must be a TensorProtocol')
        if value.ndim != len(self._size):
            raise ValueError(f'{self._name} must have {len(self._size)} dimensions')
        for i, (required_size, actual_size) in enumerate(zip(self._size, value.shape)):
            if required_size == '*': continue
            if isinstance(required_size, int):
                if required_size == actual_size: continue
                # mat = TensorValidator[2, 2]  # in class definition
                # self.mat = np.zeros((3, 2))  # error
                raise ValueError(f'the {i}-th dimension of {self._name} must have size {required_size}')
            elif isinstance(required_size, slice):
                if required_size.start is None and required_size.stop is None and required_size.step is None:
                    # mat = TensorValidator[:, 2], ':' means any size on 0-th dimension.
                    continue
                min_size = required_size.start or 0
                max_size = required_size.stop or float('inf')
                if required_size.step is not None:
                    '''
                    mat = TensorValidator[0::2]
                    self.mat = np.zeros((0, 2))  # right
                    self.mat = np.zeros((1, 2))  # error
                    self.mat = np.zeros((2, 2))  # right
                    self.mat = np.zeros((3, 2))  # error
                    '''
                    ...  # TODO: step is not supported yet.
                if min_size <= actual_size < max_size: continue
                # mat = TensorValidator[3:5, 2]
                # self.mat = np.zeros((2, 2))  # error
                raise ValueError(f'the {i}-th dimension of {self._name} must have size in range [{min_size}, {max_size})')
            elif isinstance(required_size, str):
                
                if ':' in required_size:
                    if required_size.count(':') != 1:
                        # mat = TensorValidator['a:b:30', 2]  # error
                        raise ValueError(f'string size must have only one ":", walrus operator and typehints is not allowed.')
                    splits = required_size.split(':')
                    min_size = _parse_str(splits[0], mapping=mapping, actual_size=actual_size) if splits[0] else 0
                    max_size = _parse_str(splits[1], mapping=mapping, actual_size=actual_size) if splits[1] else float('inf')
                    if max_size < min_size:
                        raise ValueError(f'In "a:b" format, "a" must be less than or equal to "b"')
                    if min_size <= actual_size < max_size: continue
                    raise ValueError(f'the {i}-th dimension of {self._name} must have size in range [{min_size}, {max_size})')
                required_size_int = _parse_str(required_size, mapping=mapping, actual_size=actual_size)
                if actual_size == required_size_int: continue
                raise ValueError(f'the {i}-th dimension of {self._name} must have size {required_size_int}')
            else:
                raise TypeError(f'{self._name} size must be int or slice or str')

class _TensorLike:
    __instance: _TensorLike | None = None
    
    def __new__(cls, *args, **kwargs):
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance
    
    def __getitem__(self, size: tuple[int | slice | str, ...] | int | slice | str) -> _TensorValidator:
        if isinstance(size, tuple):
            return _TensorValidator(size)
        else:
            return _TensorValidator((size,))
    
TensorLike = _TensorLike()

'''
```python
@check_arg(0)[3:4, 2:3]  # the 0-th arg a will be validated as `[3:4, 2:3]`
@check_arg('b')[2:3, 3:4]  # b will be validated as `[2:3, 3:4]`
@check_ret[2, 3]  # return value will be validated as `[2, 3]`
def foo(a: NDArray, b: NDArray):
    ...
    
@check_arg[1:, :10]  # the 0-th arg a will be validated as `[1:, :10]`
@check_ret(2)[2, 3]  # return value should be a tuple, and the 2-th element should be validated as `[2, 3]`
def bar(a: NDArray, b: NDArray):
    ...
    
@check_arg[...] be used with @check_arg[...], will same as @check_arg(0)[...], @check_arg(1)[...],
@check_ret[...] be used with @check_ret[...], will same as @check_ret(0)[...], @check_ret(1)[...],
@check_arg(0)[...] cannot be used with @check_arg
@check_ret(0)[...] cannot be used with @check_ret
```
'''





def _check[**P, R](func: Callable[P, R]):
    if hasattr(func, '__tensor_check__'):
        return func
    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        seq_arg_check: bool = getattr(func, '__seq_arg_check__', False)  # if use @check_arg[...], seq_check will be True.
        var_arg_check: bool = getattr(func, '__var_arg_check__', False)  # if use @check_arg(0)[...] or @check_arg('a')[...], args_checkers will be True.
        onc_ret_check: bool = getattr(func, '__onc_ret_check__', False)  # if use @check_ret[...], seq_check will be True.
        tup_ret_check: bool = getattr(func, '__tup_ret_check__', False)  # if use @check_ret(0)[...], tup_check will be True.
        mapping: dict[str, int] = {}
        if seq_arg_check:
            seq_validators: list[_TensorValidator] = getattr(func, '__seq_arg_validators__', [])
            for i, arg in enumerate(args):
                seq_validators[i](mapping, arg)
        if var_arg_check:
            var_validators: dict[str | int, _TensorValidator] = getattr(func, '__var_arg_validators__', {})
            for key, validator in var_validators.items():
                if isinstance(key, int):
                    validator(mapping, args[key])
                else:
                    validator(mapping, kwargs[key])
        ret = func(*args, **kwargs)
        if onc_ret_check:
            onc_ret_validator: _TensorValidator = getattr(func, '__onc_ret_validator__')
            onc_ret_validator(mapping, ret)
        if tup_ret_check:
            if not isinstance(ret, tuple):
                raise TypeError(f'Return value of {func.__name__} should be a tuple')
            tup_ret_validators: dict[int, _TensorValidator] = getattr(func, '__tup_ret_validators__', {})
            for i, validator in tup_ret_validators.items():
                validator(mapping, ret[i])
        return ret
    wrapper.__tensor_check__ = True  # type: ignore
    return wrapper



import numpy as np

class Test:
    
    mat_0 = TensorLike[2, 5:9]
    mat_1 = TensorLike['a', 'b']
    mat_2 = TensorLike[':a']
    
    def __init__(self) -> None:
        self.mat_0 = np.zeros((2, 2))
        self.mat_1 = np.zeros((2, 9))
        self.mat_2 = np.zeros((9,))
        
        
if __name__ == '__main__':
    t = Test()
