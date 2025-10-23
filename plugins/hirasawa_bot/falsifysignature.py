from typing import Callable, Mapping
from inspect import signature, Parameter, Signature, _empty
from functools import partial
    
    
def flatten_args(max_num = 16, remove: bool = True):
    '''
    return a decorator to falsify the signature of `func` by flattening the args.
    ```python
    @flatten_args(remove=True)
    def func(a: int, *args):
        ...
    # will be falsified as `(a: int, args_0, args_1, ..., args_15)` default max_num is 16.
    
    @flatten_args(max_num=8):
    def func(a: int, *args: str):
        ...
    # will be falsified as `(a: int, args_0: str, args_1: str, ..., args_7: str, *args: str)`
    # args_n will be annotated as `str`
    
    
    @flatten_args(args_name='arguments')
    def func(a: int, *args: str):
        ...
    # do nothing, because args_name you provided is 'arguments', and var args name is 'args'
    
    @flatten_args(args_name='arguments')
    def func(a: int, *args: str):
        ...
    # will be falsified as `(a: int, arguments_0: str, arguments_1: str, ..., arguments_15: str, *args: str)`
    
    ```
    '''
    def decorator(func: Callable) -> Callable:
        params_signature: Signature = signature(func)
        params_mapping: Mapping[str, Parameter] = params_signature.parameters
        params_name: list[str] = [name for name in params_mapping]
        params_sequence: list[Parameter] = [params_mapping[name] for name in params_name]
        params_annotations: dict[str, type] = func.__annotations__
        var_args_index = next(filter(
            lambda index: params_sequence[index].kind == Parameter.VAR_POSITIONAL,
            range(len(params_sequence))
        ), -1)
        if var_args_index == -1:
            return func
        var_args_name = params_name[var_args_index]
        var_args_type = params_annotations.get(params_name[var_args_index], None)
        if remove:
            del params_sequence[var_args_index]
            del params_name[var_args_index]
            params_annotations.pop(var_args_name)
        for i in range(max_num):
            arg_name = f'args_{max_num - i - 1}'
            if arg_name in params_name:
                raise ValueError(f'Parameter `{arg_name}` already exists')
            params_sequence.insert(var_args_index, Parameter(arg_name, Parameter.POSITIONAL_OR_KEYWORD, annotation=var_args_type))
            params_name.insert(var_args_index, arg_name)
            if var_args_type is None: continue
            params_annotations[arg_name] = var_args_type
        func.__signature__ = params_signature.replace(parameters=params_sequence)  # type: ignore
        func.__annotations__.update(params_annotations)
        return func
    return decorator

    
def flatten_kwargs(
    remove_kwargs: bool = False,
    **kwargs: type
) -> Callable[[Callable], Callable]:
    '''
    @flatten_kwargs(a=int, b=str)
    def func(**kwargs):
        ...
    # will be falsified as `(a: int, b: str, **kwargs)`
    '''
    def decorator(func: Callable) -> Callable:
        params_signature: Signature = signature(func)
        params_mapping: Mapping[str, Parameter] = params_signature.parameters
        params_name: list[str] = [name for name in params_mapping]
        params_sequence: list[Parameter] = [params_mapping[name] for name in params_name]
        params_annotations: dict[str, type] = func.__annotations__
        if params_sequence[-1].kind != Parameter.VAR_KEYWORD:
            return func
        if remove_kwargs:
            params_sequence.pop()
            params_name.pop()
        for name, annotation in kwargs.items():
            if name in params_name:
                raise ValueError(f'Parameter `{name}` already exists')
            params_sequence.append(Parameter(name, Parameter.KEYWORD_ONLY, annotation=annotation))
            params_name.append(name)
            params_annotations[name] = annotation
        func.__signature__ = params_signature.replace(parameters=params_sequence)  # type: ignore
        func.__annotations__.update(params_annotations)
        return func
    return decorator


def append_keyargs(
    name: str,
    annotation: type | None = None,
    default: object | None = None,
) -> Callable[[Callable], Callable]:
    def decorator(func: Callable) -> Callable:
        params_signature: Signature = signature(func)
        params_mapping: Mapping[str, Parameter] = params_signature.parameters
        params_name: list[str] = [name for name in params_mapping]
        params_sequence: list[Parameter] = [params_mapping[name] for name in params_name]
        params_annotations: dict[str, type] = func.__annotations__
        if name in params_name:
            index = params_name.index(name)
            del params_sequence[index]
            del params_name[index]
            params_annotations.pop(name)
        params_sequence.append(Parameter(
            name,
            Parameter.KEYWORD_ONLY,
            default=default or _empty,
            annotation=annotation or _empty,
        ))
        params_name.append(name)
        if annotation is not None:
            params_annotations[name] = annotation
        func.__signature__ = params_signature.replace(parameters=params_sequence)  # type: ignore
        func.__annotations__.update(params_annotations)
        return func
    return decorator

    