from __future__ import annotations

from functools import wraps
from pathlib import Path
from warnings import deprecated  # type: ignore

from typing import (
    Iterator,
    AsyncIterator,
    Any,
    Callable,
    Awaitable,
    Concatenate,
    Optional,
    Protocol,
    runtime_checkable,
)

from dataclasses import dataclass
from jinja2 import Environment, FileSystemLoader, Template


from ncatbot.plugin_system import (
    NcatBotPlugin,
    option,
    admin_filter,
    root_filter,
    group_filter,
    command_registry,
)

from ncatbot.core.message import (
    GroupMessage,
)

from ncatbot.core.event import (
    BaseMessageEvent,
    MessageSegment,
    MessageArray,
    Image,
    Text,
    At,
    File,
    Video,
)


from ncatbot.utils import get_log, status, assets
from ncatbot.plugin_system.builtin_plugin.unified_registry.command_system.utils.specs import CommandSpec

from .falsifysignature import flatten_args, flatten_kwargs, append_keyargs


type ItemType = str | int | float | bool | Path | MessageSegment
logger = get_log()
permissions: dict[str, int] = {}


class MyAt(At):
    __add__ = lambda self, other: MessageArray(self, Text(text=f' {other}'))


class MessageEventProtocol(Protocol):
    message_type: str
    group_id: str
    user_id: str


@dataclass
class MessageEventDuck:
    message_type: str
    group_id: str
    user_id: str

    
type NcatBotSyncGeneratorMethod[**P] = Callable[
    Concatenate[NcatBotPlugin, MessageEventProtocol, P],
    Iterator[ItemType] | AsyncIterator[ItemType] | ItemType | None,
]

type NcatBotAwaitableMethod[**P] = Callable[
    Concatenate[NcatBotPlugin, MessageEventProtocol, P],
    Awaitable[None],
]

type HirasawaMethod[**P] = Callable[
    Concatenate[NcatBotPlugin, MessageEventProtocol, P],
    AsyncIterator[ItemType] | Awaitable[ItemType] | Awaitable[None]
]

def get_command_spec(method: Callable) -> CommandSpec | None:
    '''
    返回方法对象对应注册在插件中的CommandSpec对象
    若该方法未注册为命令，则返回None
    '''
    commands = command_registry.get_all_commands()
    for key in commands:
        if commands[key].func.__qualname__ == method.__qualname__:
            return commands[key]
    return None


def get_role_level(user_id: str) -> int:
    '''
    根据用户ID获取用户权限
    '''
    if status.global_access_manager.user_has_role(user_id, assets.PermissionGroup.ROOT.value):
        return 0
    if status.global_access_manager.user_has_role(user_id, assets.PermissionGroup.ADMIN.value):
        return 1
    if status.global_access_manager.user_has_role(user_id, assets.PermissionGroup.USER.value):
        return 2
    return 1024


def get_user_info(arg: str, history: list[dict[str, Any]], sender_id: str) -> str:
    if arg.startswith('At(qq="') and arg.endswith('")'):
        return arg[7:-2]
    if arg == '':
        return sender_id
    if not arg.isdigit():
        return 'invalid'
    if len(arg) > 3:
        return arg
    num = int(arg)
    if num < 0:
        return 'invalid'
    if num == 0:
        return sender_id
    return history[-num]['sender_id']


def load_prompts(jinja2_root: Path) -> dict[str, Template]:
    ans = {}
    env = Environment(loader=FileSystemLoader(str(jinja2_root)))
    for file in jinja2_root.glob('*.j2'):
        ans[file.stem] = env.get_template(file.name)
    return ans
    

def parse2array(
    item: ItemType | list[ItemType] | tuple[ItemType, ...],
    event: BaseMessageEvent | None = None  # this arg is for future use
) -> MessageArray:
    if isinstance(item, MessageArray):
        return item
    elif isinstance(item, MessageSegment):
        return MessageArray(item)
    elif isinstance(item, (list, tuple)):
        return MessageArray(*map(parse2array, item))
    elif isinstance(item, Path):
        if not item.exists():
            raise FileNotFoundError(f"File not found: {item}")
        if item.is_dir():
            raise IsADirectoryError(f"Is a directory: {item}")
        if item.suffix in {'.jpg', '.png', '.jpeg'}:
            return MessageArray(Image(file=str(item.absolute())))
        if item.suffix in {'.mp4', '.mov', '.avi', '.flv'}:
            return MessageArray(Video(file=str(item.absolute())))
        return MessageArray(File(file=str(item.absolute()), file_name=item.name))
    else:
        text = str(item)
        return MessageArray(Text(text=text[0:256 if len(text) > 256 else len(text)]))


def hirasawa[**P](method: HirasawaMethod[P]) -> NcatBotAwaitableMethod[P]:
    '''
    method should be a async generator, or a couroutine function.
    '''
    @hirasawa_option.help('显示帮助信息')
    @flatten_args(remove=True)  # remove *args and **kwargs in signature
    @flatten_kwargs(remove_kwargs=True)
    @wraps(method)
    async def wrapper(
        self: NcatBotPlugin,
        event: MessageEventDuck, *args: P.args, **kwargs: P.kwargs) -> None:
        result = method(self, event, *args, **kwargs)
        send_id: str
        send_msg: Callable[[str | int, list[dict]], Awaitable[str]]
        if event.message_type == 'group':
            send_msg = self.api.send_group_msg_sync
            send_id = event.group_id
        elif event.message_type == 'private':
            send_msg = self.api.send_private_msg_sync
            send_id = event.user_id
        else:
            raise TypeError(f"Unsupported event type: {event.message_type}")
        if isinstance(result, Awaitable):
            await_result: ItemType | None = await result
            if await_result is None:
                return
            msg = parse2array(await_result)
            send_msg(send_id, msg.to_list())
            return
        async for item in result:
            msg = parse2array(item)
            send_msg(send_id, msg.to_list())
    return wrapper


class OptionDecoratorFactory(Protocol):
    def __call__(
        self,
        help: Optional[str] = ...,  # 可选参数（有默认值）
        short_name: Optional[str] = ...,  # 可选参数（有默认值）
        long_name: Optional[str] = ...,  # 可选参数（有默认值）
    ) -> Callable[[Callable], Callable]:
        ...


type MyOption = Callable[
    [str],
    Callable[[NcatBotAwaitableMethod], NcatBotAwaitableMethod]
]


class _OptionGetter:
    
    _instance: _OptionGetter | None = None  # singleton instance
    
    def __new__(cls):
        if cls._instance != None:
            return cls._instance
        cls._instance = super().__new__(cls)
        return cls._instance
    
    def __getattr__(self, option_name: str) -> MyOption:
        def my_option(
            desc: str = "",
        ) -> Callable[[NcatBotAwaitableMethod], NcatBotAwaitableMethod]:
            # return option(short_name=option_name[0], long_name=option_name, help=desc)
            def decorator(func: NcatBotAwaitableMethod) -> NcatBotAwaitableMethod:
                @option(short_name=option_name[0], long_name=option_name, help=desc)
                @append_keyargs(name=option_name, annotation=bool, default=False)
                @wraps(func)
                async def wrapper(self: NcatBotPlugin, event: BaseMessageEvent, *args, **kwargs):
                    return await func(self, event, *args, **kwargs)
                return wrapper
            return decorator
        return my_option

hirasawa_option = _OptionGetter()

@deprecated('Use `hirasawa` instead.')
def hirasawa_command(name: str | None = None, aliases: list | None = None, description: str = "", permission: str = 'user', **kwargs):
    def decorator(generator):
        nonlocal name, aliases, description
        name = name if name is not None else generator.__name__
        description = description if description != "" else generator.__doc__
        permission_level = ('root', 'admin', 'user').index(permission)
        if permission_level == -1:
            permission_level = 1024  # 防止自己打错字
        permissions[name] = permission_level
        @wraps(generator)
        @group_filter
        @command_registry.command(name, aliases, description, **kwargs)
        @option(short_name='h', long_name='help', help='显示帮助信息')
        @wraps(generator)
        async def wrapper(self: NcatBotPlugin, event: GroupMessage, *args: tuple, **kwargs: dict):
            if kwargs.get('help', False):
                self.api.post_group_msg_sync(
                    group_id=event.group_id,
                    at=event.sender.user_id,
                    text=f"\n指令'{name}'的使用方式：\n{description}"
                )
                return
            group_id = event.group_id
            sender_id = event.sender.user_id
            command_spec = get_command_spec(generator)
            if hasattr(self, '__pre_command__'):
                flag = await self.__pre_command__(event, command_spec, *args, **kwargs)
                if not flag:
                    return
            try:
                gen = generator(self, event, *args, **kwargs)
            except TypeError:
                await self.api.post_group_msg(
                    group_id=group_id,
                    at=sender_id,
                    text=f" 指令'{name}'参数错误，请检查命令参数"
                )
                return
            for item in gen:
                if isinstance(item, AsyncIterator):
                    async for sub_item in item:
                        seg = parse2array(sub_item)
                        self.api.send_group_msg_sync(group_id, seg.to_list())
                    continue
                seg = parse2array(item)
                self.api.send_group_msg_sync(group_id, seg.to_list())
                # self.api.send_group_msg_sync(group_id, seg.to_list())
            if hasattr(self, '__post_command__'):
                await self.__post_command__(event, command_spec, *args, **kwargs)
        if permission == 'root':
            return root_filter(wrapper)
        elif permission == 'admin':
            return admin_filter(wrapper)
        return wrapper
    return decorator


