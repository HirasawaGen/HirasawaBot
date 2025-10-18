from typing import Callable, Any
from functools import wraps
from __future__ import annotations


def register(name: str, description: str = '', flag: bool = False):
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args, **kwargs):
            print(f'This func is registered as `{name}`.')
            print(f'Description: {description}')
            if flag:
                print('The test flag is opened.')
            return func(*args, **kwargs)
        return wrapper
    return decorator


class DecoratorFactory:
    # singleton pattern
    _instance: DecoratorFactory | None = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __getattr__(self, name: str) -> Callable[[str, bool], Callable]:
        def decorator(description: str = 'no description', flag: bool = True):
            return register(name, description, flag)
        return decorator


factory = DecoratorFactory()

@register('some_thing', 'This is a test function.', True)
def bar():
    print('bar')


@factory.some_thing('This is a test function.')  # type: ignore
def foo():
    print('foo')
