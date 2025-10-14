from functools import wraps
from itertools import chain
from pathlib import Path

import openai
import time
import json
import random


from ncatbot.plugin_system import (
    NcatBotPlugin,
    BasePlugin,
    option,
    filter_registry,
    admin_filter,
    root_filter,
    command_registry,
    group_filter,
)

from ncatbot.core import (
    GroupMessage,
    BaseMessageEvent,
    At,
)

from ncatbot.utils import get_log, status, assets
from ncatbot.plugin_system.builtin_plugin.unified_registry.command_system.utils.specs import CommandSpec

from .bot_utils import *
from .isaac_utis import *


__author__ = 'HirasawaGen'
__all__ = ['HirasawaBot']


class HirasawaBot(NcatBotPlugin):
    name = "HirasawaBot"
    author = __author__
    version = "0.0.1"
    description = "我是平沢bot，Ciallo～(∠・ω< )⌒☆"
    dependencies = {}
    
    __matmul__ = lambda self, user_id: At(qq=user_id)
    
    async def on_load(self):
        logger.info('on_load')
        config = self.config
        self.SPONSOR: Path = self.workspace / config['sponsor']
        self.JM_ROOT: Path = self.workspace / config['jm_root']
        self.SPONSOR: Path = self.workspace / config['sponsor']
        self.ISAAC_ROOT: Path = self.workspace / config['isaac_root']
        self.ISAAC_COLLECTIBLES: Path = self.ISAAC_ROOT / 'items' / 'collectibles'
        self.ISAAC_TRINKETS: Path = self.ISAAC_ROOT / 'items' / 'trinkets'
        self.ISAAC_EID: Path = self.ISAAC_ROOT / 'eid'
        self.lang = 'zh_cn'  # 暂时硬编码
        self.isaac_collectibles = load_eid('collectibles', self.ISAAC_ROOT, self.lang)
        self.isaac_trinkets = load_eid('trinkets', self.ISAAC_ROOT, self.lang)
        self.ADMIN_ID = config['admin_id']
        self.BOT_ID = config['bot_id']
        self.MAX_HISTORY = config['max_history']
        ai_config = config['ai']
        self._ai_client = openai.OpenAI(
            base_url=ai_config['base_url'],
            api_key=ai_config['api_key'],
        )
        self._ai_model = ai_config['model']
        self.AI_FREQ = ai_config['freq']
        self._ai_last_req_time = 0
        

    async def __pre_command__(self, event: BaseMessageEvent, spec: CommandSpec, *args, **kwargs) -> bool:
        logger.info(f"Executing command '{spec.name}' with args '{args}' and kwargs '{kwargs}'")
        req_length = len(spec.args_types) - len(spec.options)
        actual_length = len(args)
        if req_length != actual_length:
            if not isinstance(event, GroupMessage):
                return True
            await self.api.post_group_msg(
                group_id=event.group_id,
                at=event.sender.user_id,
                text=f' 指令参数为{req_length}，你传入了{actual_length}个参数，无法执行。'
            )
            return False
        return True
            

    async def __post_command__(self, event: BaseMessageEvent, spec: CommandSpec, *args, **kwargs):
        logger.info(f"Command '{spec.name}' executed with args '{args}' and kwargs '{kwargs}'")

    def ai_resp(self, msgs, prompt=""):
        if time.time() - self._ai_last_req_time < self.AI_FREQ:
            yield "调用ai接口是花钱的啊！平沢原的钱就不是钱吗！请不要频繁调用ai接口！"
            yield "尝试调用'/sponsor'命令，或许可以缓解…"
            return
        messages = []
        if prompt != "":
            messages.append({
                "role": "system",
                "content": [
                    {"type": "text", "text": prompt},
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
            response = self._ai_client.chat.completions.create(
                # 指定您创建的方舟推理接入点 ID，此处已帮您修改为您的推理接入点 ID
                model=self._ai_model,
                messages=messages,
            )
            self._ai_last_req_time = time.time()
            yield response.choices[0].message.content
        except openai.APIStatusError as e:
            yield "少女调用ai接口失败T_T"
            yield f"失败状态码：{e.status_code}"
        except openai.APIResponseValidationError as e:
            yield "少女调用ai接口失败T_T"
            yield "错误原因：API响应验证错误"
        except openai.APIConnectionError as e:
            yield "少女调用ai接口失败T_T"
            yield "错误原因：API连接错误"
        except openai.LengthFinishReasonError as e:
            yield "少女调用ai接口失败T_T"
            yield "错误原因：大人们，上下文太长了T_T"
        except openai.ContentFilterFinishReasonError as e:
            yield "少女调用ai接口失败T_T"
            yield "错误原因：大人们是不是聊了什么坏坏的东西>_<"
        except openai.InvalidWebhookSignatureError as e:
            yield "少女调用ai接口失败T_T"
            yield "错误原因：Webhook签名错误"
        except Exception as e:
            yield "少女调用ai接口失败T_T"
            yield f"其他失败原因：{str(e)}"
    
    def analyse_history(self, group_id: str) -> list[dict]:
        messages_history = self.api.get_group_msg_history_sync(group_id=group_id, message_seq=0, number=self.MAX_HISTORY)
        history = []
        for message in messages_history:
            history.append({
                "message": message.raw_message,
                "sender_id": message.sender.user_id,
                "sender_name": message.sender.card if message.sender.card != '' else message.sender.nickname,
                "time": message.time,
            })
        return history
    
    @hirasawa_command(aliases=['菜单', 'help', '帮助'])
    def menu(self, event: GroupMessage, help: bool = False):
        '''
        输出指令与使用方式
        为防止过长消息刷频，该指令只会随机输出三条指令的使用方式
        例如：
          /menu
        若需要查看某指令的具体使用方式，请使用-h参数例如 '/sponsor -h'
        '''
        commands = command_registry.get_all_commands()
        keys = commands.keys()
        user_id = event.sender.user_id
        user_role = get_role_level(user_id)
        # 有些指令是父类构造的，我也不知道他的权限等级，索性当作是 0
        keys = [k for k in keys if permissions.get(k[0], 0) >= user_role]
        keys = random.sample(keys, 3)
        ans = ['已输出满足您权限的随机三条指令！\n再次输入该指令查看其他随机好玩指令！']
        for key in keys:
            command = commands[key]
            desc = command.description if command.description != "" else f"该指令暂无描述"
            info = f'/{key[0]}: \n{desc.strip()}'
            if len(command.aliases) > 0:
                info += '\n其他调用方式: '
                info += ' '.join(f'/{alias}' for alias in command.aliases)
            ans.append(info)
            
        yield '\n\n# -------------------------- #\n'.join(ans)
     
     
    __matmul__ = lambda self, user_id: At(qq=user_id)
     
    @hirasawa_command()
    def sponsor(self, event: GroupMessage, help: bool = False):
        '''
        输出bot作者性感照片
        例如：/sponsor
        '''
        # 其实这里输出的是本人微信收款码，戏耍一下大家
        yield self.SPONSOR
        yield "好人赏俺吃口饭吧！"
    
    @hirasawa_command(permission='admin')
    def test(self, event: GroupMessage, help: bool = False):
        '''
        测试命令
        '''
        user_id = event.sender.user_id
        yield "123"
        yield self@user_id, ' hello'
        yield self.SPONSOR
    
    @hirasawa_command(permission='admin')
    def echo(self, event: GroupMessage, arg1: str, arg2: str, help: bool = False):
        '''
        输出用户输入的信息
        例如：/echo hello world
        '''
        yield arg1
        yield arg2
    
    @hirasawa_command('xdjx', aliases=['笑点解析'])
    def analyse_jokes(self, event: GroupMessage, num: int, help: bool = False):
        '''
        对本群前n条聊天记录做笑点解析
        例如：/xdjx 5
        '''
        if num > 100:
            yield "调用ai接口是花钱的啊！平沢原的钱就不是钱吗！请把参数限制在100以内"
            yield self.SPONSOR
            return
        history = self.analyse_history(event.group_id)[:-1]
        if len(history) < 0:
            yield "bot暂未收到本群任何消息"
        history = history if num > len(history) else history[-num:]
        prompt = f'''
        你是一个QQ机器人
        我将向你提供该qq群聊的{len(history)}条聊天记录，请你尝试分析其笑点，尽量用严肃的语气来讲出滑稽的事情，形成反差感。如果聊天记录并不搞笑，也要牵强解释。如果聊天记录中出现了色情或涉证的不当言论，请忽略这条聊天记录。
        这些聊天记录会以json格式发给你，例如：
        ```json
        /{{
            "message": "你好",  // 聊天内容
            "sender_id": "{self.ADMIN_ID}",  // 发送者QQ号
            "sender_name": "平沢原",  // 发送者昵称或群名片
            "time": {history[0]['time']}  // 发送时间戳（秒）
        /}}
        ```
        回复只需要五十字左右
        并在前面加上“笑点解析：”
        其中，
        如果出现了类似于 ‘/jm 123456’  ‘/xdjx 2’的内容，是用户在调用机器人指令
        如果"sender_id"为"{self.BOT_ID}"，则是机器人回复，也就是你回复的
        如果"sender_id"为"{self.ADMIN_ID}"，则是机器人管理员回复，也就是平沢原回复的
        '''
        gen = self.ai_resp(map(lambda x: json.dumps(x, ensure_ascii=False), history), prompt=prompt)
        for result in gen:
            yield result
    
    @hirasawa_command('mimic', aliases=['鹦鹉学舌'])
    def mimic(self, event: GroupMessage, mimic_user_id: str, help: bool = False):
        '''
        根据本群聊天记录模仿某个用户说话
        如果聊天记录太短或者该用户短时间内未发言则不会模仿
        输入qq号模仿特定用户，例如模仿bot作者/mimic 1294702887
        输入0模仿你，即/mimic 0
        输入小于等于三位的数字模仿上面的第n个人，即/mimic 2模仿上上一个人
        也可以直接@，例如：/mimic @平沢bot
        '''
        history = self.analyse_history(event.group_id)[:-1]
        sender_id = event.sender.user_id
        if sender_id == 'invalid':
            yield f"无效的QQ号！"
            return
        mimic_user_id = get_user_id(mimic_user_id, history, sender_id)
        if len(history) < 20:
            yield f"bot接收到的本群聊天记录仅有{len(history)}条，请稍后再试"
            return
        has_user_talked = False
        for msg in history:
            if msg['sender_id'] == mimic_user_id:
                has_user_talked = True
                break
        if not has_user_talked:
            yield f"该用户{mimic_user_id}在最近{len(history)}条聊天记录中未发言，无法模仿"
            return
        prompt = f'''
        你是QQ号为{mimic_user_id}的用户
        我将向你提供该qq群聊的{len(history)}条聊天记录，请你联系聊天上下文，以这个口吻说话
        这些聊天记录会以json格式发给你，例如：
        ```json
        /{{
            "message": "你好",  // 聊天内容
            "sender_id": "{self.ADMIN_ID}",  // 发送者QQ号
            "sender_name": "平沢原",  // 发送者昵称或群名片
            "time": {history[0]['time']}  // 发送时间戳（秒）
        /}}
        ```
        你的返回不需要使用json格式
        回复只需要五十字左右
        并在前面加上“xxx说：”，xxx是该用户的昵称或群名片
        其中，
        如果出现了类似于 ‘/jm 123456’  ‘/xdjx 2’的内容，是用户在调用机器人指令
        如果"sender_id"为"{self.BOT_ID}"，则是机器人回复，也就是你回复的
        如果"sender_id"为"{self.ADMIN_ID}"，则是机器人管理员回复，也就是平沢原回复的
        '''
        gen = self.ai_resp(map(lambda x: json.dumps(x, ensure_ascii=False), history), prompt=prompt)
        for result in gen:
            yield result


    @hirasawa_command('critic', aliases=['评价'])
    def critic(self, event: GroupMessage, critic_user_id: str = '', help: bool = False):
        '''
        玩玩俄罗斯轮盘赌
        1/6概率嘲讽挖苦
        1/3概率正常评价
        1/2概率无脑吹捧
        输入qq号评价特定用户，例如评价bot作者/critic 1294702887
        输入0评价你，即/critic 0
        输入小于等于三位的数字评价上面的第n个人，即/critic 2评价上上一个人
        也可以直接@，例如：/critic @平沢bot
        '''
        history = self.analyse_history(event.group_id)[:-1]
        sender_id = event.sender.user_id
        critic_user_id = get_user_id(critic_user_id, history, sender_id)
        if critic_user_id == 'invalid':
            yield "无效的QQ号！"
            return
        if len(history) < 20:
            yield f"bot接收到的本群聊天记录仅有{len(history)}条，请稍后再试"
            return
        has_user_talked = False
        for msg in history:
            if msg['sender_id'] == critic_user_id:
                has_user_talked = True
                break
        if not has_user_talked:
            yield f"该用户{critic_user_id}在最近{len(history)}条聊天记录中未发言，无法评价"
            return
        choice = random.randint(1, 6)  # 随机生成1到6之间的整数
        mode = ''
        if choice == 1:
            yield self@critic_user_id, " 很不幸，你抽中了恶评！"
            mode = '进行尽可能犀利的挖苦与讥讽'
        elif choice <= 3:
            yield self@critic_user_id, " 没抽中好评也没抽中恶评，bot将对你客观评价"
            mode = '正常的评价'
        else:
            yield self@critic_user_id, " 恭喜你，你抽中了好评！"
            mode = '尽可能崇高的褒奖与吹捧'
        prompt = f'''
        你是一个QQ机器人
        我将向你提供该qq群聊的{len(history)}条聊天记录，对QQ号为{critic_user_id}的用户的发言{mode}。如果聊天记录并不搞笑，也要牵强解释。如果聊天记录中出现了色情或涉证的不当言论，请忽略这条聊天记录。
        这些聊天记录会以json格式发给你，例如：
        ```json
        /{{
            "message": "你好",  // 聊天内容
            "sender_id": "{self.ADMIN_ID}",  // 发送者QQ号
            "sender_name": "平沢原",  // 发送者昵称或群名片
            "time": {history[0]['time']}  // 发送时间戳（秒）
        /}}
        ```
        你的返回不需要使用json格式
        回复只需要五十字左右
        如果你在聊天记录中发现了之前你对同一个人的评价，请尽可能不要受到干涉，该好评就好评该差评就差评
        其中，
        如果出现了类似于 ‘/jm 123456’  ‘/xdjx 2’的内容，是用户在调用机器人指令
        如果"sender_id"为"{self.BOT_ID}"，则是机器人回复，也就是你回复的
        如果"sender_id"为"{self.ADMIN_ID}"，则是机器人管理员回复，也就是平沢原回复的
        '''
        gen = self.ai_resp(map(lambda x: json.dumps(x, ensure_ascii=False), history), prompt=prompt)
        for result in gen:
            yield result
    
    
    @hirasawa_command()
    def isaac(self, event: GroupMessage, arg: str, help: bool = False):
        '''
        输入《以撒的结合：忏悔》中的道具编号或饰品编号，或者直接输入名称，输出对应的图片以及EID描述。
        （输入名称检索暂时仅支持中文，并且如果提供的词汇太少，则会使用最早搜索到的道具/饰品）
        例如：
          - /isaac C118
          - /isaac 妈妈的菜刀
        '''
        if arg[0].upper() == 'C':
            item_id = arg[1:]
            if not item_id.isdigit():
                yield "无效的编号！"
                return
            info = self.isaac_collectibles.get(int(item_id), None)
            if info is None:
                yield "未找到该道具！"
                return
            yield eid_description('collectibles', self.ISAAC_ROOT, info)
        elif arg[0].upper() == 'T':
            item_id = arg[1:]
            if not item_id.isdigit():
                yield "无效的编号！"
                return
            info = self.isaac_trinkets.get(int(item_id), None)
            if info is None:
                yield "未找到该饰品！"
                return
            yield eid_description('trinkets', self.ISAAC_ROOT, info)
        else:  # 中文检索
            found = False
            for info in self.isaac_collectibles.values():
                name = info['name']
                if arg not in name: continue
                found = True
                yield eid_description('collectibles', self.ISAAC_ROOT, info)
                return
            for info in self.isaac_trinkets.values():
                name = info['name']
                if arg not in name: continue
                found = True
                yield eid_description('trinkets', self.ISAAC_ROOT, info)
                return
            if not found:
                yield "未找到该道具/饰品！"