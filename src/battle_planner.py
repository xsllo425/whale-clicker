"""自动战斗决策原型：只产生建议，不采集画面，也不发送输入。"""
from dataclasses import dataclass
from typing import FrozenSet, Mapping, Optional, Tuple


@dataclass(frozen=True)
class BattleView:
    timestamp: float
    character: Optional[str]
    confidence: float
    focused: bool
    in_combat: bool
    user_holding: bool
    ready_skills: FrozenSet[str]


@dataclass(frozen=True)
class CharacterProfile:
    skill_priority: Tuple[str, ...]
    attack_interval: float = 0.3


class BattlePlanner:
    """对识别结果进行防误触判断；未接入 UI 和真实游戏。"""
    def __init__(self, profiles: Mapping[str, CharacterProfile], max_age=0.5, min_confidence=0.9):
        self.profiles = dict(profiles)
        self.max_age = max_age
        self.min_confidence = min_confidence
        self.enabled = False
        self._reset()

    def _reset(self):
        self._character = None
        self._stable_count = 0
        self._last_frame = None
        self._last_action = float('-inf')
        self._pending = set()

    def start(self):
        self._reset()
        self.enabled = True

    def stop(self):
        self.enabled = False
        self._reset()

    def decide(self, view: BattleView, now: float):
        if not self.enabled:
            return None
        fresh = 0 <= now - view.timestamp <= self.max_age
        valid = (fresh and view.focused and view.in_combat and not view.user_holding
                 and view.confidence >= self.min_confidence and view.character in self.profiles)
        if not valid:
            self._reset()
            return None
        if self._last_frame is not None and view.timestamp <= self._last_frame:
            return None
        self._last_frame = view.timestamp
        if view.character != self._character:
            self._character = view.character
            self._stable_count = 1
            self._pending.clear()
            return None
        self._stable_count += 1
        if self._stable_count < 2:
            return None
        profile = self.profiles[view.character]
        self._pending.intersection_update(view.ready_skills)
        if now - self._last_action < max(0.1, profile.attack_interval):
            return None
        for skill in profile.skill_priority:
            if skill in view.ready_skills and skill not in self._pending:
                self._pending.add(skill)
                self._last_action = now
                return skill
        self._last_action = now
        return 'attack'
