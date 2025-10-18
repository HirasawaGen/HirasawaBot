from typing import Callable, Literal
import inspect


def falsify_sig(func: Callable):
    '''        
    ```python
    @falsify_sig
    def my_func(a: int, b: str, c: bool = False) -> None: ...
    # raise an error, because there isn't define a func named '__replace__func' or '__append__func'
    
    @falisfy_sig
    def __replace__func(a: int, b: str, c: bool = False) -> str: ...
    @falsify_sig
    def func(*args, **kwargs):
        ...
    # the signature of func will be falsified as `(a: int, b: str, c: bool = False)`
    
    @falsify_sig
    def __append__func(text: str, flag: bool = False, **kwargs) -> str: ...
    @falsify_sig
    def func(a: int, b: str) -> int:
        ...
    # the signature of func will be falsified as `(a: int, b: str, text: str, flag: bool = False, **kwargs) -> int`
    # return type of `__append__func` will be ignored. but if `func` didn't annotated return type, it will be `str`, which is the return type of `func`
    
    @falsify_sig
    def __replace__func(a: int, b: str, c: bool) -> bool: ...
    @falsify_sig
    def __append__func(text: str, flag: bool = False, **kwargs) -> str: ...
    @falsify_sig
    def func(foo: Foo, bar: Bar) -> int:
        ...
    # the signature of func will be falsified as `(a: int, b: str, c: bool, text: str, flag: bool = False **kwargs) -> bool`
    
    @falsify_sig
    def __replace__replace_func(a: int, b: str, c: bool) -> bool: ...
    @falsify_sig
    def __replace__func(*args, **kwargs):
        ...
    # __replace__func' signature will not be falsified, because `falisy` will wonder `__replace__func` is used to fasify `func`
    
    ```
    '''
    ...
    
    
def flatten_args(args_name: str = 'agrs', max_num = 16, remove: bool = False):
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
    ...
    
    
def flatten_kwargs(kwargs_name: str = 'kwargs', max_num = 16, remove: bool = False):
    '''
    
    '''
    ...
    