from __future__ import annotations

from typing import Protocol, Literal, Iterator
import random
import time
import math


# 尽量让这个类可以不依赖于ncatbot独立使用
class Sender(Protocol):
    @property
    def sender_id(self) -> str: ...



class WhoIsSpy:
    # enable each group only have one instance of WhoIsSpy
    _instances: dict[str, WhoIsSpy] = {}
    
    def __new__(
        cls,
        game_id: str,
        preparing_time: int = 10,  # 默认等待10s
        max_players: int = 10,  # 默认最多10人
        min_players: int = 4,  # 默认最少4人
    ) -> WhoIsSpy:
        if game_id in cls._instances:
            return cls._instances[game_id]
        instance = super().__new__(cls)
        cls._instances[game_id] = instance
        return instance
    
    def __init__(
        self,
        game_id: str,
        preparing_time: int = 10,  # 默认等待10s
        playing_time: int = 60,  # 默认游戏时间60s
        max_players: int = 10,  # 默认最多10人
        min_players: int = 4,  # 默认最少4人
    ):
        self._game_id = game_id
        self._period: Literal['preparing', 'playing', 'finished'] = 'finished'
        self._players: list[Sender] = []
        self._spy_indices: list[int] = []
        self._last_add_time: float = 0.0  # 上次新玩家加入时间
        self._start_time: float = 0.0  # 游戏开始时间
        self._votes: dict[str, int] = {}
        
    def choose_spy(self, spy_num: int=-1):
        '''
        -1 means choose math.floor(1/4) of players as spy
        '''
        spy_num = spy_num if spy_num >= 0 else math.floor(len(self._players) / 4)
        
    def __len__(self) -> int:
        return len(self._players)
    
    def get_spies(self) -> list[Sender]:
        return [self._players[i] for i in self._spy_indices]
    
    def get_regulars(self) -> list[Sender]:
        return [self._players[i] for i in range(len(self._players)) if i not in self._spy_indices]
    
    def time_callback(self):
        '''
        定时器回调函数，用于更新游戏状态
        如果是游戏准备阶段，并且当前时间距离上一次新玩家加入已经经过了self.prapering_time秒，就终止游戏
        '''
        if self.period == 'preparing':
            if time.time() - self.last_add_time > self.preparing_time:
                self.period = 'finished'
                return
        if self.period == 'playing':
            if time.time() - self.start_time > self.playing_time:
                self.period = 'finished'
                return
    
    @property
    def game_id(self) -> str:
        return self._game_id
    
    @property
    def period(self) -> Literal['preparing', 'playing', 'finished']:
        return self._period
    
    @period.setter
    def period(self, value: Literal['preparing', 'playing', 'finished']):
        self._period = value
        if value == 'finished':
            self._players = []
            self._spy_indices = []
            self._last_add_time = 0.0
            self._start_time = 0.0
        if value == 'playing':
            self._start_time = time.time()
        
    def add_player(self, player: Sender) -> str:
        if self.period == 'playing':
            return '游戏已经开始，不能加入'
        if self.period == 'finished':  # 游戏未开启，开启游戏
            self.period = 'preparing'
            self._players.append(player)
            self.last_add_time = time.time()
            return "游戏开始，请等待其他玩家加入"
        if self._period == 'preparing':  # 等待准备
            if player.sender_id in {p.sender_id for p in self._players}:
                return '你已经加入了游戏，请不要重复加入'
            self.last_add_time = time.time()
            self._players.append(player)
            return "您已成功加入游戏"
        raise ValueError('Unknown period')
    
    def vote_spy(self, player: Sender):
        if not self._period == 'playing':
            raise ValueError('游戏未开始')
        
    
        
        
    
    