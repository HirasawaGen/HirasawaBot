from pathlib import Path
from typing import Any
import random

from ncatbot.core import BotClient, GroupMessage, MessageArray
from ncatbot.core.event.message_segment import Forward
from ncatbot.utils import get_log, run_coroutine
from ncatbot.core.event.message_segment import MessageSegment

from commands import commands
from yaml import safe_load, safe_dump

import cv2
import json
from cv2.typing import MatLike


config: dict = safe_load(Path('hirasawa_config.yaml').read_text())
ADMIN_ID = config['admin_id']  # 管理员 QQ 号
BOT_ID = config['bot_id']  # 机器人 QQ 号
MAX_HISTORY = 100
bot = BotClient()
logger = get_log()


histories: dict[str, Any] = {
    
}


@bot.on_shutdown()
async def on_shutdown(*args):
    await bot.api.post_private_msg(user_id=ADMIN_ID, text='机器人已启动！')
    

@bot.on_startup()
async def on_startup(*args):
    await bot.api.post_private_msg(user_id=ADMIN_ID, text='机器人已启动！')



def parse_elem(elem, context=None):
    if elem is None: return []
    if context is None: context = {}
    messages = []
    
    if isinstance(elem, MessageSegment):
        messages = [elem.to_dict()]
    elif isinstance(elem, list):
        for sub_elem in elem:
            new_messages = parse_elem(sub_elem)
            if len(new_messages) == 0: continue
            if len(new_messages) == 1 and new_messages[0]['type'] == 'file':
                continue
            messages.extend(new_messages)
    elif isinstance(elem, dict):
        return [elem]
    elif isinstance(elem, Path):
        if elem.is_dir(): return
        if elem.suffix in {'.jpg', '.png', '.jpeg'}:
            messages =  [{"type": "image", "data": {"file": str(elem.absolute())}}]
        else:
            messages [{"type": "file", "data": {"file": str(elem.absolute()), "name": elem.name}}]
    elif isinstance(elem, MatLike):
        temp = Path() / 'temp.jpg'
        cv2.imwrite(str(temp.absolute()), elem)
        messages = [{"type": "image", "data": {"file": str(temp.absolute())}}]
    else:
        messages = [{"type": "text", "data": {"text": str(elem)}}]
    return messages
            

@bot.on_group_message()
async def on_group_message(msg: GroupMessage):
    sender = msg.sender
    sender_id = sender.user_id
    group_id = msg.group_id
    msg_list: list[dict] = msg.message.to_list()
    history_path = Path() / 'histories' / f'{group_id}.yaml'
    history = histories.get(str(group_id), [] if not history_path.exists() else safe_load(history_path.open('r', encoding='utf-8')))
    history.append({
        "message": msg.raw_message,
        "sender_id": sender_id,
        "sender_name": sender.card if sender.card != '' else sender.nickname,
        "time": msg.time,
    })
    if len(history) > MAX_HISTORY:
        history = history[-MAX_HISTORY:]
    histories[group_id] = history
    
    context = {
        'group_id': group_id,
        'sender_id': sender_id,
        'history': history,
    }
    
    count = 0
    has_admin_speak = False
    for history_elem in history[::-1]:
        if history_elem['sender_id'] != BOT_ID:
            count += 1
        if history_elem['sender_id'] == ADMIN_ID:
            has_admin_speak = True
        if count > 0 and has_admin_speak:
            break
        
    if random.random() < 1 - (0.99) ** (count + 1):
        if has_admin_speak:
            gen = commands(f'/mimic {ADMIN_ID}', context=context)
        else:
            gen = commands(f'/mimic {sender_id}', context=context)
        next(gen)
        for elem in gen:
            bot.api.post_group_msg(group_id=group_id, message=str(parse_elem(elem, context=context)))
            
    
    safe_dump(history, history_path.open('w', encoding='utf-8'))
    if len(msg_list) != 2: return
    if msg_list[0]['type'] != 'at' or msg_list[0]['data']['qq'] != BOT_ID:
        return
    if msg_list[1]['type'] != 'text':
        return
    text = msg_list[1]['data']['text']
    
    try:
        gen = commands(text, context=context)
        if not gen: return
        for elem in gen:
            if isinstance(elem, Forward):
                await bot.api.post_group_forward_msg(group_id=group_id, forward=elem)
                logger.info(f"forward a message to '{group_id}'")
                continue
            message = parse_elem(elem, context=context)
            if len(message) == 0: continue
            if len(message) == 1 and message[0]['type'] == 'file':
                run_coroutine(bot.api.async_callback, "/send_group_msg", {"group_id": group_id, "message": message})
            await bot.api.async_callback(
                "/send_group_msg",
                {"group_id": group_id, "message": message},
            )
    except Exception as e:
        await bot.api.post_group_msg(group_id=group_id, at=sender_id, text=f"指令执行失败：{e}")


if __name__ == '__main__':
    try:
        bot.run()
    except KeyboardInterrupt:
        logger.info('KeyboardInterrupt')