from typing import Any, Callable


class CommandExecutor(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def __call__(self, command_str: str):
        command_str = command_str.strip()
        print(f"执行指令：{command_str}")
        command_name = command_str.split()[0]
        if not command_name[0] == "/": return
        args_str = command_str[len(command_name) + 1:]
        command_name = command_name[1:]
        if not command_name in self:
            raise KeyError(f"不存在指令：'/{command_name}'")
        args = self[command_name]['parser'](args_str)
        return self[command_name]['generator'](*args)    
    
    def register(self, command_name: str | None = None, parser: Callable[[str], Any] | None = None):
        '''
        有指定parser就用指定的
        没有就用转字符串
        如果函数逻辑太复杂也可以用装饰器注册
        '''
        def decorator(func):
            nonlocal command_name
            if command_name == None:
                command_name = func.__name__
            if not command_name in self:
                self[command_name] = {'parser': parser, 'func': None}
            if self[command_name]['parser'] == None:
                self[command_name]['parser'] = lambda x: str(x).split()
            self[command_name]['doc'] = func.__doc__
            self[command_name]['generator'] = func
            return func
        return decorator

    def register_parser(self, command_name: str):
        if not command_name in self:
            raise ValueError(f"Command {command_name} not found.")
        def decorator(func):
            self[command_name]['parser'] = func
            return func
        return decorator