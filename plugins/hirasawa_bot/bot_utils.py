from functools import wraps
from pathlib import Path
from typing import Iterable, Any, Callable, Coroutine, Literal

from ncatbot.plugin_system import (
    NcatBotPlugin,
    option,
    admin_filter,
    root_filter,
    command_registry,
    group_filter,
)

from ncatbot.core import (
    GroupMessage,
    MessageSegment,
    MessageArray,
    Image,
    Text,
    At,
    File,
)


from ncatbot.utils import get_log, status, assets
from ncatbot.plugin_system.builtin_plugin.unified_registry.command_system.utils.specs import CommandSpec


logger = get_log()
permissions: dict[str, int] = {}


def parse2segment(item) -> MessageSegment | MessageArray:
    if isinstance(item, list) or isinstance(item, tuple):
        return MessageArray([_parse2segment(i) for i in item])
    return _parse2segment(item)


def _parse2segment(item) -> MessageSegment | MessageArray:
    if isinstance(item, MessageSegment):
        return item
    elif isinstance(item, MessageArray):
        return item
    elif isinstance(item, Path):
        if not item.exists():
            raise FileNotFoundError(f"File not found: {item}")
        if item.is_dir():
            raise IsADirectoryError(f"Is a directory: {item}")
        if item.suffix in {'.jpg', '.png', '.jpeg'}:
            return Image(file=str(item.absolute()))
        return File(file=str(item.absolute()), file_name=item.name)
    else:
        return Text(text=str(item))


def parse_message(item) -> list[dict]:
    messages = []
    if isinstance(item, MessageSegment):
        messages = [item.to_dict()]
    elif isinstance(item, MessageArray):
        messages = item.to_list()
    elif isinstance(item, dict):
        messages = [item]
    elif isinstance(item, Path):
        if not item.exists():
            raise FileNotFoundError(f"File not found: {item}")
        if item.is_dir():
            raise IsADirectoryError(f"Is a directory: {item}")
        if item.suffix in {'.jpg', '.png', '.jpeg'}:
            messages =  [{"type": "image", "data": {"file": str(item.absolute())}}]
        else:
            messages [{"type": "file", "data": {"file": str(item.absolute()), "name": item.name}}]
    else:
        messages = [{"type": "text", "data": {"text": str(item)}}]
    return messages


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


def get_user_id(arg: str, history: list[dict[str, Any]], sender_id: str) -> str:
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
    

def hirasawa_command(name: str = None, aliases: list = None, description: str = "", permission: str = 'user', **kwargs):
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
                await self.api.post_group_msg(
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
                seg = parse2segment(item)
                if isinstance(seg, MessageSegment):
                    await self.api.send_group_msg(group_id, [seg.to_dict()])
                elif isinstance(seg, MessageArray):
                    await self.api.send_group_msg(group_id, seg.to_list())
            if hasattr(self, '__post_command__'):
                await self.__post_command__(event, command_spec, *args, **kwargs)
        if permission == 'root':
            return root_filter(wrapper)
        elif permission == 'admin':
            return admin_filter(wrapper)
        return wrapper
    return decorator