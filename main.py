from pathlib import Path
import asyncio
import sys
from io import StringIO
import string
import random

from ncatbot.core import BotClient, GroupMessage
from ncatbot.utils import get_log

import jmcomic
from jmcomic import download_album

import pyzipper

from command_executor import CommandExecutor


option = jmcomic.create_option_by_file('./jm_option.yml')
ADMIN_ID = "1294702887"  # 管理员 QQ 号
BOT_ID = "3632575137"  # 机器人 QQ 号
bot = BotClient()
logger = get_log()
command = CommandExecutor()
JM_ROOT = Path() / 'jm_download'


ecchi_groups = {
    '327997077',
    '611497546',
}


@command.register()
def help(*args):
    '''
    输出帮助信息
    '''
    keys = command.keys() if len(args) == 0 else args
    result = ""
    for key in keys:
        if key not in command:
            result += f"{key}：指令不存在\n"
        result += f"{key}：{command[key]['doc']}\n"
    yield result


@command.register()
def echo(*args):
    '''
    输出用户输入的信息
    '''
    for arg in args:
        yield arg


@command.register()
def jm(jm_album_id: str):
    '''
    输入禁漫编号，下载该漫画
    并将压缩包上传到群里
    同一个本子每次下载，解压码极有可能不同！
    '''
    yield "少女下载本子中…"
    detail, _ = download_album(jm_album_id, option=option)
    ans = ""
    ans += f'下载完毕！\n'
    ans += f'本子名称：{detail.name}\n'
    ans += f'漫画作者：{'+'.join(detail.authors)}\n'
    ans += f'点赞数：{detail.likes}\n'
    ans += f'标签：{"; ".join(detail.tags)}'
    yield ans
    zipf = pyzipper.AESZipFile(f'{JM_ROOT / detail.name}.zip','w', compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES)
    all_chars = string.ascii_letters + string.digits
    password = ''.join(random.choices(all_chars, k=8))
    yield f'本子解压缩密码："{password}"'
    zipf.setpassword(password.encode('utf-8')) 
    for file in (JM_ROOT / detail.name).iterdir():
        if file.is_dir(): continue
        zipf.write(str(file))
    zipf.close()
    yield JM_ROOT / f"{detail.name}.zip"
    yield "请欣赏本子吧！"
    

close = False
@command.register()
def python(*code_parts):
    '''
    执行Python代码，拥有独立的命名空间
    例如: /python print(1+1)
    对于没有输出功能的语句，输出一个空格
    '''
    # 组合代码片段
    global close
    if close:
        yield "python 命令已关闭"
    code = ' '.join(code_parts)
    if code == 'exit!':
        close = True
        yield "python 命令已关闭"
    if not code:
        return
    
    # 初始化独立的命名空间（仅在首次调用时）
    if not hasattr(python, 'isolated_globals'):
        # 创建完全独立的命名空间
        python.isolated_globals = {
            '__builtins__': __builtins__
        }
        python.isolated_locals = {}
    
    # 捕获标准输出和错误
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    sys.stdout = captured_output = StringIO()
    sys.stderr = captured_error = StringIO()
    
    result = None
    # 先尝试作为表达式执行（有返回值）
    try:
        result = eval(code, python.isolated_globals, python.isolated_locals)
    except SyntaxError:
        # 如果不是表达式，作为语句块执行
        exec(code, python.isolated_globals, python.isolated_locals)
    finally:
        # 恢复标准输出和错误
        sys.stdout = old_stdout
        sys.stderr = old_stderr
    
    # 收集输出结果
    output = captured_output.getvalue()
    error = captured_error.getvalue()
    
    # 返回结果
    if output:
        yield f"{output}"
    if error:
        yield f"{error}"
    if result is not None and not output:
        yield f"{result}"
    else:
        yield " "


@bot.on_group_message()
async def on_group_message(msg: GroupMessage):
    sender = msg.sender
    sender_id = sender.user_id
    group_id = msg.group_id
    msg_list: list[dict] = msg.message.to_list()
    if len(msg_list) != 2: return
    if msg_list[0]['type'] != 'at' or msg_list[0]['data']['qq'] != BOT_ID:
        return
    if msg_list[1]['type'] != 'text':
        return
    text = msg_list[1]['data']['text']
    try:
        gen = command(text)
        if not gen: return
        for elem in gen:
            if isinstance(elem, Path):
                asyncio.create_task(
                    bot.api.send_group_file(
                        group_id=group_id, 
                        file=str(elem), 
                        name=elem.name
                    )
                )
                continue
            await bot.api.post_group_msg(group_id=group_id, text=f"{str(elem)}")
    except KeyError as e:
        await bot.api.post_group_msg(group_id=group_id, at=sender_id, text=str(e))
    except Exception as e:
        await bot.api.post_group_msg(group_id=group_id, at=sender_id, text=f"指令执行失败：{e}")




if __name__ == '__main__':
    bot.run()