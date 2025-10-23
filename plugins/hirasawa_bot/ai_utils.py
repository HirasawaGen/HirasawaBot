import time
from openai import AsyncOpenAI, OpenAI
from openai.types.chat import ChatCompletion
from typing import Any, Iterator, Final
from abc import ABC, abstractmethod


class Requirable[T](ABC):
    @abstractmethod
    def __call__(self, *args, **kwargs) -> T: ... # enable Callable
    def __lshift__(self, content: dict[str, Any]) -> T: return self(**content)


class AsyncRequirable[T](ABC):
    @abstractmethod
    async def __call__(self, *args, **kwargs) -> T: ... # enable Callable
    async def __lshift__(self, content: dict[str, Any]) -> T: return await self(**content)

'''
you can call:
```python
foo: Requirable
resp = foo(a=1, b=2)
```
as
```python
foo: Requirable
resp = foo << {
    'a': 1,
    'b': 2
}
```

you can also extend `requests` lib be like:
```python
my_web = Web(ip='127.0.0.1', port=8080)
resp = my_web['/index.html'] << {
    # request parameters
}
```
'''
    
class HirasawaAsyncAI(AsyncOpenAI, AsyncRequirable):
    def __init__(self, *, model: str, frequency: float = 1.0,  **kwargs) -> None:
        super().__init__(**kwargs)
        self._frequency: Final[float] = frequency
        self._last_request_time: float = 0.0
        self._model: str = model
    
    async def __call__(self, messages: Iterator[str], prompt: str = "", index: int = 0, **kwargs):
        assert time.time() - self._last_request_time > self._frequency, "Too frequent requests"
        req_messages: list = []
        if prompt != "":
            req_messages.append({
                "role": "system",
                "content": [
                    {"type": "text", "text": prompt}
                ],
            })
        for msg in messages:
            req_messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": msg}
                ],
            })
        resp = await self.chat.completions.create(
            model=self._model,
            messages=req_messages,
            **kwargs
        )
        self._last_request_time = time.time()
        return resp.choices[index].message.content
        

class HirasawaAI(OpenAI, Requirable):
    def __init__(self, *, model: str, frequency: float = 1.0, **kwargs) -> None:
        super().__init__(**kwargs)
        self._frequency: Final[float] = frequency
        self._last_request_time: float = 0.0
        self._model: str = model
    
    def __call__(self, messages: Iterator[str], prompt: str = "", index: int = 0, **kwargs):
        assert time.time() - self._last_request_time > self._frequency, "Too frequent requests"
        req_messages: list = []
        if prompt != "":
            req_messages.append({
                "role": "system",
                "content": [
                    {"type": "text", "text": prompt}
                ],
            })
        req_messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": '\n'.join(messages)}
            ],
        })
        resp: ChatCompletion = self.chat.completions.create(
            model=self._model,
            messages=req_messages,
            **kwargs
        )
        self._last_request_time = time.time()
        content = resp.choices[index].message.content
        assert content != "", "Empty response"
        assert isinstance(content, str), f"Invalid response type: {type(content)}"
        return content