# 待办

- **鸣潮自动战斗（暂缓，用户 2026-11-14 决定先不做）**：目标是按一次热键持续自动普攻/放技能，再按停止；队伍心、穗穗、雷主，默认键位。
  已有：`src/battle_planner.py`（决策原型，未接入）、`core.send_key_event` / `hold_key_until`（可中断按键，退出必抬起）及对应自测。
  缺：实时取帧（Codex 验证过 windows-capture 的 Windows Graphics Capture 可读到游戏窗口，注意按游戏进程选窗口，有同名隐藏窗口；该库为第三方依赖，与 README「纯标准库」冲突，未决）、头像/技能状态识别、热键启停与界面接入、按键配置。
  Codex 的探针与参考帧在 `E:\CODEX\2026-11-14\e-work-whale-clicker-2\work\`。
  风险：官方对宏/自动挂机有处罚声明，用户已知情。
