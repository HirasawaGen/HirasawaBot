import asyncio
from typing import AsyncIterator, Callable, Awaitable
from functools import wraps
from time import time


type ElemType = str | int | float



def parse(arg: ElemType) -> str:
    if isinstance(arg, str):
        return arg
    elif isinstance(arg, int):
        return f'int: {arg}'
    elif isinstance(arg, float):
        return f'float: {arg}'
    else:
        raise TypeError(f'Unsupported type: {type(arg)}')

def to_awaitable[**P](func: Callable[P, AsyncIterator[ElemType] | ElemType]) -> Callable[P, Awaitable[None]]:
    @wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> None:
        result: AsyncIterator[ElemType] | ElemType = func(*args, **kwargs)
        if not isinstance(result, AsyncIterator):
            return print(parse(result))
        async for elem in result:
            print(parse(elem))
    return wrapper

@to_awaitable
async def sleep(seconds: float) -> AsyncIterator[ElemType]:
    yield 'sleeping'
    yield seconds
    await asyncio.sleep(seconds)
    yield 'wake up'


async def main():
    ...

if __name__ == '__main__':
    asyncio.run(main())