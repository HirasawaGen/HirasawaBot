from functools import wraps
from itertools import chain
from itertools import batched
from pathlib import Path

from pypinyin import pinyin, Style
import openai
import time
import json
import random
from typing import Iterator, Final



from ncatbot.plugin_system import (
    NcatBotPlugin,
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
    RequestEvent,
)

from ncatbot.utils import get_log, run_coroutine
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
    dependencies: dict = {}
    
    __matmul__ = lambda self, user_id: MyAt(qq=user_id)
        
    async def on_load(self) -> None:
        logger.info('on_load')
        config = self.config
        self.SPONSOR: Path = self.workspace / config['sponsor']
        self.JM_ROOT: Path = self.workspace / config['jm_root']
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
        self.POP_FREQ = config['pop_freq']
        self.TEST_GROUP = config['test_group']
        self.promts = load_prompts(self.workspace / config['prompts_root'])
        ai_config = config['ai']
        self._ai_client = openai.OpenAI(
            base_url=ai_config['base_url'],
            api_key=ai_config['api_key'],
        )
        self._ai_model = ai_config['model']
        self.AI_FREQ = ai_config['freq']
        self._ai_last_req_time = 0
        self.pop_texts = [
            "我是平沢bot，Ciallo～(∠・ω< )⌒☆~",
            "极品人机冒泡儿~",
            "潜水党偷看中……",
        ]
        # await self.api.post_private_msg(user_id=self.ADMIN_ID, text='平沢bot已启动！')
        

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

    @on_request
    async def on_request(self, event: RequestEvent):
        if not event.is_friend_request(): return
        await event.approve()
        self.api.send_private_text_sync(user_id=event.user_id, text='你好，我是平沢bot，Ciallo～(∠・ω< )⌒☆')
        self.log2admin(f"同意了好友请求：{event.user_id}")

    def heyiwei(self, event: GroupMessage):
        if event.sender.user_id == event.self_id: return
        raw_text = event.raw_message.strip()
        if len(raw_text) < 3: return
        for word in batched(raw_text, 3):
            if pinyin(''.join(word), style=Style.NORMAL) != [['he'], ['yi'], ['wei']]: continue
            yield "何意味？"
            yield False
            return
    
    def caicaibei(self, event: GroupMessage):
        if event.sender.user_id == event.self_id: return
        raw_text = event.raw_message.strip()
        if len(raw_text) != 3: return
        if raw_text[0] != raw_text[1]: return
        if pinyin(raw_text, Style.FIRST_LETTER, errors='replace') != [['c'], ['c'], ['b']]:
            return
        yield f'老爷爷，我给你{raw_text[-2]}{raw_text[-1]}来咯！'
        yield False

    def group_pop(self, event: GroupMessage):
        if event.sender.user_id == event.self_id: return
        group_id = event.group_id
        pop_freq = self.POP_FREQ if group_id != self.TEST_GROUP else 8
        history = self.analyse_history(group_id)
        if len(history) <= pop_freq:
            return
        has_root_talked = False
        for msg in history[-1:-1-pop_freq:-1]:
            if msg['sender_id'] == event.self_id:
                return
            if msg['sender_id'] == self.ADMIN_ID:
                has_root_talked = True
        if not has_root_talked:
            pop_text = random.choice(self.pop_texts)
            yield pop_text
            yield False
            return
        self.log2admin(f'正在尝试在群{group_id}中鹦鹉学舌')
        prompt = self.promts['group_pop'].render(
            history=history,
            ADMIN_ID=self.ADMIN_ID,
            BOT_ID=self.BOT_ID,
        )
        gen = self.ai_resp(map(lambda x: json.dumps(x, ensure_ascii=False), history), prompt=prompt)
        texts = [text for text in gen]
        if len(texts) != 2:
            self.log2admin('\n'.join(texts[1:]))
            return
        yield texts[1]
        yield False

    @group_filter
    @hirasawa_deco
    def on_group_message(self, event: GroupMessage, help: bool=False) -> Iterator[ItemType]:
        for item in chain(
            self.heyiwei(event),
            self.caicaibei(event),
            self.group_pop(event),
        ):
            if item == False:
                break
            if item == True:
                continue
            yield item
        

    def log2admin(self, msg: str):
        self.api.post_private_msg_sync(user_id=self.ADMIN_ID, text=msg)
        
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
            if e.status_code == 403:
                yield "平沢原的火山引擎账号没钱了喵T_T"
                yield "或许可以调用/sponsor命令缓解财政危机？！！"
                return
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
     
    
    @hirasawa_command()
    def sponsor(self, event: GroupMessage, help: bool = False):
        '''
        输出bot作者性感照片
        例如：/sponsor
        '''
        # 其实这里输出的是本人微信收款码，戏耍一下大家
        yield self.SPONSOR
        yield "好人赏俺吃口饭吧！"
    
    
        
    
    @hirasawa_command('xdjx', aliases=['笑点解析'])
    def analyse_jokes(self, event: GroupMessage, num: int, help: bool = False):
        '''
        对本群前n条聊天记录做笑点解析
        例如：/xdjx 5
        '''
        if num > self.MAX_HISTORY // 2:
            yield f"调用ai接口是花钱的啊！平沢原的钱就不是钱吗！请把参数限制在{self.MAX_HISTORY // 2}以内"
            # yield self.SPONSOR
            return
        history = self.analyse_history(event.group_id)[:-1]
        history = history if len(history) <= self.MAX_HISTORY // 2 else history[-self.MAX_HISTORY // 2:]
        if len(history) < 0:
            yield "bot暂未收到本群任何消息"
        history = history if num > len(history) else history[-num:]
        prompt = self.promts['analyse_jokes'].render(
            history=history,
            ADMIN_ID=self.ADMIN_ID,
            BOT_ID=self.BOT_ID,
        )
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
        history = history if len(history) <= self.MAX_HISTORY // 2 else history[-self.MAX_HISTORY // 2:]
        sender_id = event.sender.user_id
        if sender_id == 'invalid':
            yield f"无效的QQ号！"
            return
        mimic_user_id = get_user_info(mimic_user_id, history, sender_id)
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
        prompt = self.promts['mimic'].render(
            mimic_user_id=mimic_user_id,
            history=history,
            ADMIN_ID=self.ADMIN_ID,
            BOT_ID=self.BOT_ID,
        )
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
        history = history if len(history) <= self.MAX_HISTORY // 2 else history[-self.MAX_HISTORY // 2:]
        sender_id = event.sender.user_id
        critic_user_id = get_user_info(critic_user_id, history, sender_id)
        # 如果评价的是bot主人
        if critic_user_id == self.ADMIN_ID:
            yield "神本无相😎😎😎"
            return
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
            yield self@critic_user_id + "很不幸，你抽中了恶评！"
            mode = '进行尽可能犀利的挖苦与讥讽'
        elif choice <= 3:
            yield self@critic_user_id + "没抽中好评也没抽中恶评，bot将对你客观评价"
            mode = '正常的评价'
        else:
            yield self@critic_user_id + "恭喜你，你抽中了好评！"
            mode = '尽可能崇高的褒奖与吹捧'
        prompt = self.promts['critic'].render(
            critic_user_id=critic_user_id,
            history=history,
            mode=mode,
            ADMIN_ID=self.ADMIN_ID,
            BOT_ID=self.BOT_ID,
        )
        gen = self.ai_resp(map(lambda x: json.dumps(x, ensure_ascii=False), history), prompt=prompt)
        for result in gen:
            yield result
    
    
    @group_filter
    @command_registry.command('isaac', aliases=['以撒的结合', '以撒'])
    @hirasawa_option.help('显示帮助信息')
    @hirasawa_option.no_desc('不输出道具/饰品的描述')
    @hirasawa_deco
    def isaac(self, event: GroupMessage, arg: str, help: bool = False, no_desc: bool = False):
        '''
        输入《以撒的结合：忏悔》中的道具编号或饰品编号，或者直接输入名称，输出对应的图片以及EID描述。
        加入-n参数将不输出道具/饰品的描述
        （输入名称检索暂时仅支持中文，并且如果提供的词汇太少，则会使用最早搜索到的道具/饰品）
        例如：
          - /isaac C118
          - /isaac 妈妈的菜刀
          - /isaac -n 妈妈的菜刀
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
            yield eid_description('collectibles', self.ISAAC_ROOT, info, no_desc)
        elif arg[0].upper() == 'T':
            item_id = arg[1:]
            if not item_id.isdigit():
                yield "无效的编号！"
                return
            info = self.isaac_trinkets.get(int(item_id), None)
            if info is None:
                yield "未找到该饰品！"
                return
            yield eid_description('trinkets', self.ISAAC_ROOT, info, no_desc)
        else:  # 中文检索
            found = False
            for info in self.isaac_collectibles.values():
                name = info['name']
                if arg not in name: continue
                found = True
                yield eid_description('collectibles', self.ISAAC_ROOT, info, no_desc)
                return
            for info in self.isaac_trinkets.values():
                name = info['name']
                if arg not in name: continue
                found = True
                yield eid_description('trinkets', self.ISAAC_ROOT, info, no_desc)
                return
            if not found:
                yield "未找到该道具/饰品！"
    
    
    @group_filter
    @command_registry.command('kick')
    @option(short_name='h', long_name='help', help='显示帮助信息')
    @hirasawa_deco
    def kick(self, event: GroupMessage, help: bool=False):
        '''
        使用该指令使bot退出本群
        使用第三方bot框架,如果机器人被踢的话可能引起风控
        所以当管理员想要踢bot，不要直接踢
        请使用‘/kick’命令，（无需@机器人）
        除群聊管理员与bot主人外，其他人无法使用该命令
        '''
        group_id = event.group_id
        sender = event.sender
        user_id = sender.user_id
        role = sender.role
        if user_id == self.ADMIN_ID or role == 'owner' or role == 'admin':
            yield "正在退出群聊..."
            self.api.set_group_leave_sync(group_id)
            return
        yield "只有群管理员与bot主人可以使用该命令！"
        
    
    @root_filter
    @group_filter
    @command_registry.command('temp')
    @hirasawa_option.help('显示帮助信息')
    @hirasawa_deco
    def temp(self, event: GroupMessage, qq_id:str, text: str, help: bool=False):
        '''
        给本群某个群友发送临时会话
        只有bot管理员可以使用
        '''
        self.api.send_private_text_sync(qq_id, text)
        yield "已发送临时会话！"
        return
    
    @group_filter
    @command_registry.command('close', aliases=['shutdown', '关机'])
    @hirasawa_option.help('显示帮助信息')
    @hirasawa_deco
    def close(self, event: GroupMessage, help: bool=False):
        '''
        关闭bot，使其不再响应任何消息
        只有bot管理员可以使用
        '''
        yield "正在关闭bot..."
        self.api.bot_exit_sync()
        return

    @group_filter
    @command_registry.command('who_spy', aliases=['谁是卧底'])
    def who_spy(self, event: GroupMessage):
        '''
        
        '''
        ...
    
        
        
        
        