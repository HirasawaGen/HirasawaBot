from __future__ import annotations

from functools import wraps
from pathlib import Path
from typing import (
    Iterator,
    Any,
    Callable,
    Awaitable,
    Sequence,
    Literal,
    Concatenate,
    Optional,
    Protocol,
    Sequence,
)

from types import GenericAlias
from jinja2 import Environment, FileSystemLoader, Template
import inspect


from ncatbot.plugin_system import (
    NcatBotPlugin,
    option,
    admin_filter,
    root_filter,
    group_filter,
    on_request,
    on_notice,
    command_registry,
)

from ncatbot.core.message import (
    GroupMessage,
    PrivateMessage,
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
from .nullsafedict import NullSafeDict


type ItemType = str | int | float | bool | Path | MessageSegment
logger = get_log()
permissions: dict[str, int] = {}

class MyAt(At):
    __add__ = lambda self, other: MessageArray(self, Text(text=f' {other}'))

    
type NcatBotGeneratorMethod[**P] = Callable[
    Concatenate[NcatBotPlugin, BaseMessageEvent, P],
    Iterator[ItemType] | ItemType,
]

type NcatBotAwaitableMethod[**P] = Callable[
    Concatenate[NcatBotPlugin, BaseMessageEvent, P],
    Awaitable[None],
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
    


def parse2array(item: ItemType | Iterator[ItemType]) -> MessageArray:
    if isinstance(item, MessageArray):
        return item
    elif isinstance(item, MessageSegment):
        return MessageArray(item)
    elif isinstance(item, Iterator):
        return MessageArray(*list(item))
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


def falsify_async_sig(
    sig_dicts: Sequence[dict[str, Any]],
    mode: Literal['replace', 'extend'] = 'replace',
    skips: set[str] | None = None,
):
    '''
    return a decorator
    falsify signature and annotations of an async function
    mode: 'replace' or 'extend'
    in replace mode, the new signature replaces the old one
    in extend mode, the new signature extends the old one
    temporally can not falsify *args and **kwargs
    item of sig_dicts should be dict[str, Any], like:
    {
        # required
        'name': 'arg_name',
        # optional, if not provided, will not be set, type should be a `type` or a `str`
        'type': int,
        # optional, if not provided, will be set to POSITIONAL_OR_KEYWORD, type should be a `inspect.Parameter.kind`
        'kind': inspect.Parameter.POSITIONAL_OR_KEYWORD,
        # optional, if not provided, will not be set, recommend you provide a value as type defined in key 'type'
        'default': 123,
    }
    '''
    skips = skips or set()
    def decorator(func: Callable[..., Awaitable[Any]]):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        origin_sig = inspect.signature(func)
        origin_annotations: dict[str, type | str] = func.__annotations__
        new_params: list[inspect.Parameter]
        new_annotations: dict[str, type | str]
        if mode =='replace':
            new_params = []
            new_annotations = {}
        elif mode == 'extend':
            new_params = [origin_sig.parameters[param_name] for param_name in origin_sig.parameters]
            new_annotations = {arg_name: arg_type for arg_name, arg_type in origin_annotations.items()}
        else:
            raise ValueError(f"Unsupported mode: {mode}")
        for sig_dict in map(NullSafeDict, sig_dicts):
            if 'name' not in sig_dict:
                raise ValueError(f"sig_dict must have 'name' key: {sig_dict}")
            arg_name = sig_dict['name']
            if arg_name in skips:
                continue
            arg_type = sig_dict['type?']
            arg_kind = sig_dict['kind?'] or inspect.Parameter.POSITIONAL_OR_KEYWORD
            arg_default = sig_dict['default?'] or inspect._empty
            new_params.append(inspect.Parameter(
                arg_name,
                arg_kind,
                default=arg_default,
            ))
            new_annotations[arg_name] = arg_type
        return wrapper
    return decorator


def hirasawa_deco[**VarParams](decorated: NcatBotGeneratorMethod[VarParams]) -> NcatBotAwaitableMethod[VarParams]:
    @wraps(decorated)
    async def wrapper(
        self: NcatBotPlugin,
        event: BaseMessageEvent,
        *args: VarParams.args,
        **kwargs: VarParams.kwargs
    ) -> None:
        send_msg: Callable[[str | int, list[dict]], Awaitable[str]]
        if isinstance(event, GroupMessage):
            send_msg = self.api.send_group_msg_sync
            send_id = event.group_id
        elif isinstance(event, PrivateMessage):
            send_msg = self.api.send_private_msg_sync
            send_id = event.user_id
        else:
            raise TypeError(f"Unsupported event type: {type(event)}")
        if kwargs.get('help', False):
            send_msg(send_id, parse2array(f"该指令的使用方式：\n{decorated.__doc__}").to_list())
            return
        decorated_ret = decorated(self, event, *args, **kwargs)
        items = decorated_ret if isinstance(decorated_ret, Iterator) else [decorated_ret]
        for item in items:
            if isinstance(item, Awaitable):
                # decorated func is an async generator,
                # async generator can not await
                # so we can let the generator yield coroutine.
                await item
            seg = parse2array(item)
            send_msg(send_id, seg.to_list())
    return wrapper

def var_args(max_length: int = 16):
    '''
    ncatbot 指令注册器无法解析变长指令
    该装饰器可以篡改函数签名，把*args: tuple[str, ...]篡改为args_0: str, args_1: str, ..., args_n: str（n为max_length-1）
    将*args: tuple[str, int, str, int]篡改为args_0: str, args_1: int, arg2: str, arg3: int
    从而实现伪变长参数的效果
    '''
    def decorator[**Params](func: NcatBotAwaitableMethod[Params]):
        # 该装饰器只修改方法元数据与签名，不修改行为逻辑，所以这里直接返回
        @wraps(func)
        async def wrapper(self: NcatBotPlugin, event: BaseMessageEvent, *args: Params.args, **kwargs: Params.kwargs):
            return await func(self, event, *args, **kwargs)
        sig = inspect.signature(func)  # 获取方法的原始签名
        annotations: dict[str, type] = {}  # 用于保存参数的类型，将替换方法本来的元数据
        new_params: list[inspect.Parameter] = []  # 用于保存新的参数，将替换方法本来的签名
        # TODO:变长参数80%名字都叫args，所以可以先查一下args arg arguments argument等参数是不是变长参数，再遍历参数寻找变长参数
        for name in sig.parameters:  # 遍历原本的参数
            param = sig.parameters[name]
            if param.kind == inspect.Parameter.VAR_POSITIONAL:  # 处理*args参数
                if not isinstance(param.annotation, GenericAlias) or not isinstance(param.annotation.__origin__, type):
                    raise TypeError(f"变长参数必须得使用标注了类型的tuple，例如：*args: tuple[str, ...]，*args: tuple[int, str, int]")
                param__args__: list[type] = list(param.annotation.__args__)  # 获取*args参数的类型元组
                # 如果是tuple[str, ...]，则将其扩展为tuple后面max_length个str的类型
                if len(param__args__) == 2 and param__args__[-1] == Ellipsis:
                    param__args__ = max_length * [param__args__[0]]
                # 注入新的参数
                for i in range(len(param__args__)):
                    if param__args__[i] == Ellipsis:
                        raise TypeError(f'...只能只能用在两个参数的情况，并且位于第二个参数的位置，不能使用tuple[str, ..., int]，tuple[...]，tuple[..., bool]等类似写法')
                    new_params.append(inspect.Parameter(
                        f'{name}_{i}',
                        inspect.Parameter.POSITIONAL_OR_KEYWORD,
                        # default=None,
                        annotation=param__args__[i]
                    ))
                    annotations[f'{name}_{i}'] = param__args__[i]
                continue
            if param.kind == inspect.Parameter.VAR_KEYWORD:  # 处理**kwargs参数
                # 移除掉**kwargs，防止ncatbot报错
                continue
            new_params.append(param)
            annotations[name] = param.annotation
        if not hasattr(wrapper, '__signature__'): return wrapper  # 下面这一行不知道为什么有mypy报错，`# types: ignore`也没用
        wrapper.__signature__ = sig.replace(parameters=new_params)  # types: ignore
        wrapper.__annotations__ = annotations
        return wrapper
    return decorator


class OptionDecoratorFactory(Protocol):
    def __call__(
        self,
        help: str,
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
            return option(short_name=option_name[0], long_name=option_name, help=desc)
        return my_option

hirasawa_option = _OptionGetter()

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


