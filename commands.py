from pathlib import Path
import random
import string
import sys
from io import StringIO
import string
import random
import time

import pyzipper
import jmcomic
import cv2
import shutil
import openai
import json
from jmcomic import download_album
from yaml import safe_load, safe_dump
import numpy as np

from ncatbot.core.helper.forward_constructor import ForwardConstructor
from ncatbot.core import MessageArray
from ncatbot.core.event.message_segment import (
    Image,
    Text,
)

from command_executor import CommandExecutor
from cv_utils import obfuscation


config: dict = safe_load(Path('hirasawa_config.yaml').read_text())

option = jmcomic.create_option_by_file('./jm_option.yml')
commands = CommandExecutor()

JM_ROOT: Path = Path() / config['jm_root']
ADMIN_ID = config['admin_id']  # 管理员 QQ 号
BOT_ID = config['bot_id']  # 机器人 QQ 号
ECCHI_GROUPS = config['ecchi_groups']
SPONSOR: Path = Path() / config['sponsor']

ai_config = config['ai']

ai_client = openai.OpenAI(
    base_url=ai_config['base_url'],
    api_key=ai_config['api_key'],
)


@commands.register()
def help(context, *args):
    '''
    输出帮助信息
    有参数就输出参数对应的指令帮助信息
    否则输出所有指令帮助信息
    例如：/help echo
    '''
    keys = commands.keys() if len(args) == 0 else args
    result = ""
    for key in keys:
        if key not in commands:
            result += f"{key}：指令不存在\n"
        result += f"{key}：{commands[key]['doc']}\n"
    yield result
    
    
@commands.register()
def echo(context, *args):
    '''
    输出用户输入的信息
    例如：/echo hello world
    '''
    for arg in args:
        yield arg


@commands.register()
def jm(context, *args: str):
    '''
    输入禁漫编号，下载该漫画
    并将本子哈希混淆后发到群里
    例如：/jm 350234
    如果想要原图，加以加-z参数
    会将本子原图加密压缩后再上传
    例如：/jm -z 350234
    同一个本子每次下载，解压码极有可能不同！
    请注意：本功能仅限于色色名单群使用
    '''
    if context['group_id'] not in ECCHI_GROUPS:
        yield "不可以色色！"
        yield "请联系bot主人将本群加入色色名单"
        return
    jm_album_id = args[-1]
    doujinshi_dir = JM_ROOT / jm_album_id
    if '-c' in args and context['sender_id'] != ADMIN_ID:
        yield "你没有权限执行此命令！"
        return
    if '-c' in args and jm_album_id == 'all':
        yield "开始清理所有缓存…"
        for d in JM_ROOT.iterdir():
            if d.is_dir():
                shutil.rmtree(d, ignore_errors=True)
            else:
                d.unlink()
        yield "缓存清理完毕"
        return
    if (doujinshi_dir / 'info.yaml').exists():
        if '-c' in args:
            yield "开始清理缓存…"
            shutil.rmtree(doujinshi_dir, ignore_errors=True)
            yield "缓存清理完毕"
            return
        yield "本子已存在"
        info = safe_load((doujinshi_dir / 'info.yaml').open('r', encoding='utf-8'))
    else:
        yield "少女下载本子中…"
        if '-c' in args:
            yield "未下载该本子，请检查编号是否正确"
            return
        try:
            detail, _ = download_album(jm_album_id, option=option)
        except jmcomic.jm_exception.PartialDownloadFailedException as e:
            yield "部分下载失败，将仅上传成功下载的部分"
            yield f"失败原因：{str(e)}"
        except jmcomic.jm_exception.JmcomicException as e:
            yield f"少女下载失败T_T"
            yield f"失败原因：{e.message}"
            return
        yield "少女下载本子完毕！"
        info = {
            'name': detail.name,
            'authors': detail.authors,
            'likes': detail.likes,
            'tags': detail.tags
        }
        safe_dump(info, (doujinshi_dir / 'info.yaml').open('w', encoding='utf-8'))
    ans = ""
    ans += f'本子名称：{info["name"]}\n'
    ans += f'漫画作者：{"+".join(info["authors"])}\n'
    ans += f'点赞数：{info["likes"]}\n'
    ans += f'标签：{"; ".join(info["tags"])}'
    if '-z' in args:
        yield ans
        all_chars = string.ascii_letters + string.digits
        password = ''.join(random.choices(all_chars, k=8))
        zip_name = f'密码: "{password}" {info["name"]}.zip'
        zipf = pyzipper.AESZipFile(zip_name,'w', compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES)
        yield f'本子解压缩密码："{password}"'
        zipf.setpassword(password.encode('utf-8')) 
        for file in doujinshi_dir.iterdir():
            if file.is_dir(): continue
            zipf.write(str(file))
        zipf.close()
        yield '少女上传压缩包中…'
        yield JM_ROOT / zip_name
    else:
        fcr = ForwardConstructor(user_id=BOT_ID, nickname="HirasawaBot")
        fcr.attach(MessageArray(Text(ans)))
        for img_path in doujinshi_dir.iterdir():
            if not img_path.is_file(): continue
            if img_path.suffix not in ['.jpg', '.png', '.webp']: continue
            if img_path.name.startswith('obfuscated_'): continue
            print(img_path.name)
            obfuscated_img_path = doujinshi_dir / f'obfuscated_{img_path.stem}.jpg'
            img = cv2.imread(str(img_path.absolute()))
            if img is None:
                fcr.attach(MessageArray(Text(f'无法读取{img_path.name}，请检查文件格式')))
                continue
            obfuscated_img = obfuscation(img)
            cv2.imwrite(str(obfuscated_img_path.absolute()), obfuscated_img)
            fcr.attach(MessageArray(Image(file=str(obfuscated_img_path.absolute()))))
        fcr.attach(MessageArray(Text(f'图片已经过哈希混淆，如果需要下载本子原图，请使用"/jm -z {jm_album_id}"，然根据提示下载并解压')))
        yield '少女上传QQ合并消息中…'
        yield fcr.to_forward()
    yield "请欣赏本子吧！"
    

@commands.register()
def python(context, *code_parts):
    '''
    执行Python代码，拥有独立的命名空间
    例如: /python print(1+1)
    对于没有输出功能的语句，输出一个空格
    '''
    # 组合代码片段
    if context['sender_id'] != ADMIN_ID:
        yield "你没有权限执行此命令！"
        return
    code = ' '.join(code_parts)
    
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


@commands.register()
def sponsor(context, *args):
    '''
    输出bot作者性感照片
    例如：/sponsor
    '''
    yield SPONSOR
    yield "好人赏俺吃口饭吧！"


last_req_time = 0
freq = 3

def ai_resp(msgs, promt=""):
    global last_req_time
    if time.time() - last_req_time < freq:
        yield "调用ai接口是花钱的啊！平沢原的钱就不是钱吗！请不要频繁调用ai接口！"
        yield SPONSOR
        return
    messages = []
    if promt != "":
        messages.append({
            "role": "system",
            "content": [
                {"type": "text", "text": promt},
            ],
        })
    for msg in msgs:
        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": msg},
            ],
        })
    yield "少女调用ai接口中…"
    try:
        response = ai_client.chat.completions.create(
            # 指定您创建的方舟推理接入点 ID，此处已帮您修改为您的推理接入点 ID
            model=ai_config['model'],
            messages=messages,
        )
        yield response.choices[0].message.content
    except Exception as e:
        yield "少女调用ai接口失败T_T"
        yield f"失败原因：{str(e)}"


@commands.register('xdjx', parser=int)
def analyse_jokes(context, num):
    '''
    对本群前n条聊天记录做笑点解析
    例如：/xdjx 5
    '''
    if num > 20:
        yield "调用ai接口是花钱的啊！平沢原的钱就不是钱吗！请把参数限制在20以内"
        yield SPONSOR
    if len(context['history']) < 1:
        yield "bot暂未收到本群任何消息"
    history = context['history'][:-1]
    history = history if num > len(history) else history[-num:]
    prompt = f'''
    你是一个QQ机器人
    我将向你提供改qq群聊的{len(history)}条聊天记录，请你尝试分析其笑点，尽量用严肃的语气来讲出滑稽的事情，形成反差感。如果聊天记录并不搞笑，也要牵强解释。如果聊天记录中出现了色情或涉证的不当言论，请忽略这条聊天记录。
    这些聊天记录会以json格式发给你，例如：
    ```json
    /{{
        "message": "你好",  // 聊天内容
        "sender_id": "{ADMIN_ID}",  // 发送者QQ号
        "sender_name": "平沢原",  // 发送者昵称或群名片
        "time": {history[0]['time']}  // 发送时间戳（秒）
    /}}
    回复只需要五十字左右
    其中，
    如果出现了类似于 ‘@平沢bot jm 123456’  ‘@bot /xdjx 2’的内容，是用户在调用机器人指令
    具体可参考：{help.__doc__}
    如果"sender_id"为"{BOT_ID}"，则是机器人回复，也就是你回复的
    如果"sender_id"为"{ADMIN_ID}"，则是机器人管理员回复，也就是平沢原回复的
    ```
    '''
    gen = ai_resp(map(lambda x: json.dumps(x, ensure_ascii=False), history), promt=prompt)
    for result in gen:
        yield result


@commands.register()
def mimic(context, *args):
    '''
    根据本群聊天记录模仿某个用户说话
    如果聊天记录太短或者该用户短时间内未发言则不会模仿
    例如：/mimic 1294702887
    '''
    num = 20
    history = context['history'][:-1]
    history = history if num > len(history) else history[-num:]
    if len(history) < 20:
        yield f"bot接收到的本群聊天记录仅有{len(history)}条，请稍后再试"
        return
    mimic_user_id = args[0]
    has_user_talked = False
    for msg in history:
        if msg['sender_id'] == mimic_user_id:
            has_user_talked = True
            break
    if not has_user_talked:
        yield f"该用户{mimic_user_id}在最近{num}条聊天记录中未发言，无法模仿"
        return
    prompt = f'''
    你是一个QQ机器人
    我将向你提供改qq群聊的{len(history)}条聊天记录，请你联系聊天上下文，模仿QQ号为{mimic_user_id}的用户说话
    这些聊天记录会以json格式发给你，例如：
    ```json
    /{{
        "message": "你好",  // 聊天内容
        "sender_id": "{ADMIN_ID}",  // 发送者QQ号
        "sender_name": "平沢原",  // 发送者昵称或群名片
        "time": {history[0]['time']}  // 发送时间戳（秒）
    /}}
    你的返回不需要使用json格式
    回复只需要五十字左右
    其中，
    如果出现了类似于 ‘@平沢bot jm 123456’  ‘@bot /xdjx 2’的内容，是用户在调用机器人指令
    具体可参考：{help.__doc__}
    如果"sender_id"为"{BOT_ID}"，则是机器人回复，也就是你回复的
    如果"sender_id"为"{ADMIN_ID}"，则是机器人管理员回复，也就是平沢原回复的
    ```
    '''
    gen = ai_resp(map(lambda x: json.dumps(x, ensure_ascii=False), history), promt=prompt)
    for result in gen:
        yield result



if __name__ == '__main__':
    context = {
        'group_id': '123',
        'sender_id': '1294702887',
        'history': [
            {
                "message": "从前有座山，山里有座庙",
                "sender_id": "1294702887",
                "sender_name": "平沢原",
                "time": 1637111111,
            },
            {
                "message": "庙里有个老和尚，讲故事说：",
                "sender_id": "1294702887",
                "sender_name": "平沢原",
                "time": 1637111122,
            }
        ] * 100
    }
    command_str = '/mimic 1294702887'
    gen = commands(command_str, context=context)
    for result in gen:
        print(result)
    