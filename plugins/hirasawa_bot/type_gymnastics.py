'''
How to do Type Gymnastics in Python>=3.12
Python 3.12 passed PEP 695
So we can Fuck Type Gymnastics more Niubilable.
'''
from typing import * # all in!
from functools import wraps


# 1st, `type` can type a type.
type StrOrInt = str | int
type ObjOrCls[T] = T | type[T]
ParamSpec


# 装饰*args, **kwargs
def deco_1[**Params, Ret](func: Callable[Params, Ret]) -> Callable[Params, Ret]:
    @wraps(func)
    def wrapper(*args: Params.args, **kwargs: Params.kwargs):
        print(f'modified {func.__name__}')
        return func(*args, **kwargs)
    return wrapper


@deco_1
def func_1(a: int, b: str, c: float) -> None:
    pass


# 装饰int, *args, **kwargs，就得使用Concatenate
def deco_2[**Params, Ret](func: Callable[Concatenate[int, Params], Ret]) -> Callable[Concatenate[str, Params], Ret]:
    @wraps(func)
    def wrapper(a: str, *args: Params.args, **kwargs: Params.kwargs):
        print(f'modified {func.__name__}')
        return func(len(a), *args, **kwargs)
    return wrapper

@deco_2
def func_2(a: int, b: str, c: float) -> None:
    pass

