# -*- coding: utf-8 -*-
"""无副作用自测：不发送任何真实点击/按键。
1) 编译检查 core.py / app.py
2) SendInput 结构体尺寸（64 位应为 40）
3) 热键注册/注销（找空闲 F 键）
4) 界面构建 + 参数解析（自动让路版）
5) 长按状态机（打桩 send_button；core 保留能力）
6) 鼠标钩子路由逻辑（直接喂假结构体，不装真钩子）
7) 真·鼠标钩子装/拆（纯观察：side_enabled=False 不吞任何键）
8) 连点暂停/恢复（打桩 send_click）
9) 真实按住→自动让路→松手恢复 协同（打桩，驱动 App 方法）
"""
import os
import py_compile
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "src")
os.chdir(SRC)
sys.path.insert(0, SRC)

# CI（无交互桌面）跳过需要真实窗口/钩子的用例；本机默认全跑
HEADLESS = bool(os.environ.get("WHALE_HEADLESS")) or bool(os.environ.get("CI"))

# 1) 编译
for f in ("core.py", "app.py"):
    py_compile.compile(os.path.join(SRC, f), doraise=True)
print("[1] compile OK")

import ctypes
import core

# 2) 结构体尺寸
size = ctypes.sizeof(core.INPUT)
assert size == 40, f"INPUT size = {size}, expected 40 on x64"
print(f"[2] sizeof(INPUT) = {size} OK")

# 3) 热键注册（找一个未被占用的 F 键）
fired = []
hk = None
used_name = None
if HEADLESS:
    print("[3] skipped (headless CI)")
else:
    for i in range(12, 0, -1):
        name = f"F{i}"
        cand = core.HotkeyListener(core.VK_BY_NAME[name], lambda: fired.append(1), hotkey_id=99)
        cand.start()
        time.sleep(0.25)
        if cand.registered:
            hk, used_name = cand, name
            break
        cand.stop()
        time.sleep(0.1)
    assert hk is not None, "all F1-F12 occupied"
    print(f"[3] hotkey {used_name} registered OK")
    hk.stop()
    time.sleep(0.2)
    assert not hk.registered
    print("[3] hotkey unregistered OK")

# 4) 界面构建（不 mainloop）
import tempfile
import tkinter as tk
import app as appmod

# 测试期间的配置读写一律走临时文件，不碰用户的 config.json
appmod.CONFIG_PATH = os.path.join(tempfile.gettempdir(), "whale_clicker_test_config.json")


def close_app(a, root):
    """收尾：_on_close 已立即 destroy，这里只兜底，避免 after 落空噪音。"""
    a._on_close()
    try:
        root.update()
    except Exception:
        pass
    try:
        root.destroy()
    except Exception:
        pass


if HEADLESS:
    print("[4] skipped (headless CI)")
else:
    root = tk.Tk()
    a = appmod.App(root)
    root.update()
    time.sleep(0.3)
    if not (a.listener is not None and a.listener.registered):
        a._register_hotkey(used_name)
        time.sleep(0.3)
    assert a.listener is not None and a.listener.registered, "UI hotkey not registered"
    print("[4] UI built, hotkey registered OK")
    # 参数解析
    a.interval_var.set("50")
    assert a._parse_interval() == 50.0
    a.limit_var.set(True)
    a.count_var.set("10")
    assert a._parse_count() == 10
    print("[4] param parsing OK")
    # 新版控件：让路勾选存在，长按热键已删除；主题切换可用
    assert hasattr(a, "yield_var") and hasattr(a, "mouse_side_var") and hasattr(a, "swallow_var")
    assert not hasattr(a, "holdkey_var"), "hold hotkey should be removed"
    assert not hasattr(a, "_hold_down") and not hasattr(a, "_hold_up")
    assert hasattr(a, "theme_btn") and a.theme in ("light", "dark")
    a._toggle_theme()
    root.update()
    a._toggle_theme()
    root.update()
    print("[4] auto-yield widgets + theme toggle OK (hold-key removed)")
    # 关掉真钩子/热键，避免测试期间全局拦截（下面直接驱动方法）
    if a.hook:
        a.hook.stop()
        time.sleep(0.15)
        a.hook = None
    if a.listener:
        a.listener.stop()
        time.sleep(0.15)
        a.listener = None
    close_app(a, root)

# 5) 长按状态机（打桩 send_button，不发真实点击；core 保留能力）
events = []
orig_send = core.send_button
core.send_button = lambda button="left", down=True, pos=None: events.append((button, down))
try:
    c = core.Clicker()
    assert c.start_hold("left", None, 0.15) is True
    assert c.mode == "hold" and c.running
    time.sleep(0.05)
    assert events and events[0] == ("left", True), "hold should press down first"
    c.wait_done(1.0)
    assert not c.running
    assert events[-1] == ("left", False), "hold must release at end"
    assert events.count(("left", True)) == 1 and events.count(("left", False)) == 1
    print("[5] timed hold: down->up OK")

    events.clear()
    c2 = core.Clicker()
    assert c2.start_hold("right", (10, 20), 0.0) is True
    time.sleep(0.08)
    assert events == [("right", True)], "infinite hold stays down until stop"
    assert c2.running
    c2.stop(); c2.wait_done(1.0)
    assert not c2.running
    assert events == [("right", True), ("right", False)], "manual stop must release"
    print("[5] infinite hold + manual release OK")
finally:
    core.send_button = orig_send

# 6) 鼠标钩子路由逻辑（直接喂假结构体，不装真钩子、不吞真实按键）
log = {"side1": 0, "down": [], "up": []}
h = core.InputHookListener(
    on_side1=lambda: log.__setitem__("side1", log["side1"] + 1),
    on_button_down=lambda b: log["down"].append(b),
    on_button_up=lambda b: log["up"].append(b),
    swallow_side=True, side_enabled=True,
)
ms = core.MSLLHOOKSTRUCT()
ms.flags = 0
maddr = ctypes.addressof(ms)
# 侧键1 按下 -> on_side1，且吞掉(返回1)
ms.mouseData = core.XBUTTON1 << 16
r = h._mouse_proc(0, core.WM_XBUTTONDOWN, maddr)
assert log["side1"] == 1 and r == 1, "side1 down should fire and swallow"
# 侧键1 抬起 -> 不触发 side1，仍吞掉
r = h._mouse_proc(0, core.WM_XBUTTONUP, maddr)
assert log["side1"] == 1 and r == 1
# 侧键2 按下/抬起 -> 不触发任何回调，原样放行
ms.mouseData = core.XBUTTON2 << 16
r = h._mouse_proc(0, core.WM_XBUTTONDOWN, maddr)
assert log["side1"] == 1 and not log["down"] and r != 1, "side2 must pass through"
r = h._mouse_proc(0, core.WM_XBUTTONUP, maddr)
assert not log["up"] and r != 1
# 真实左键按下/抬起 -> 上报且放行（游戏必须收到）
r = h._mouse_proc(0, core.WM_LBUTTONDOWN, maddr)
assert log["down"] == ["left"] and r != 1, "real left down must fire AND pass through"
r = h._mouse_proc(0, core.WM_LBUTTONUP, maddr)
assert log["up"] == ["left"] and r != 1
# 右键/中键
h._mouse_proc(0, core.WM_RBUTTONDOWN, maddr)
h._mouse_proc(0, core.WM_MBUTTONDOWN, maddr)
h._mouse_proc(0, core.WM_RBUTTONUP, maddr)
h._mouse_proc(0, core.WM_MBUTTONUP, maddr)
assert log["down"] == ["left", "right", "middle"]
assert log["up"] == ["left", "right", "middle"]
# 注入事件应被完全忽略（连点器自己的点击不触发让路）
ms.flags = core.LLMHF_INJECTED
h._mouse_proc(0, core.WM_LBUTTONDOWN, maddr)
h._mouse_proc(0, core.WM_LBUTTONUP, maddr)
assert log["down"] == ["left", "right", "middle"], "injected clicks must be ignored"
assert log["up"] == ["left", "right", "middle"]
ms.mouseData = core.XBUTTON1 << 16
r = h._mouse_proc(0, core.WM_XBUTTONDOWN, maddr)
assert log["side1"] == 1, "injected side1 must be ignored"
ms.flags = 0
# swallow_side=False 时侧键1仍触发但不吞
h.swallow_side = False
r = h._mouse_proc(0, core.WM_XBUTTONDOWN, maddr)
assert log["side1"] == 2 and r != 1, "swallow off should pass through"
h.swallow_side = True
# side_enabled=False 时侧键1不触发也不吞（运行时热改）
h.side_enabled = False
r = h._mouse_proc(0, core.WM_XBUTTONDOWN, maddr)
assert log["side1"] == 2 and r != 1, "side disabled must pass through"
h.side_enabled = True
print("[6] hook routing (side1/side2 pass, real buttons pass, inject-ignore, hot-toggle) OK")

# 7) 真·鼠标钩子装/拆（纯观察模式：不启用侧键、不吞任何键，零干扰）
if HEADLESS:
    print("[7] skipped (headless CI)")
else:
    h2 = core.InputHookListener(swallow_side=False, side_enabled=False)
    h2.start()
    time.sleep(0.3)
    assert h2.installed, f"mouse hook install failed, err={h2.error}"
    h2.stop()
    time.sleep(0.2)
    assert not h2.installed
    print("[7] real mouse hook install/uninstall OK")

# 8) 连点暂停/恢复（打桩 send_click）
clicks = []
orig_click = core.send_click
core.send_click = lambda button="left", pos=None: clicks.append(1)
try:
    c = core.Clicker()
    assert c.start(0.02, "left", None, 0) is True
    time.sleep(0.12)
    n1 = c.count_done
    assert n1 >= 2, f"should have clicked, got {n1}"
    c.pause()
    time.sleep(0.06)
    snap = c.count_done
    time.sleep(0.12)
    assert c.count_done == snap, "paused clicker must not click"
    assert c.paused
    c.resume()
    time.sleep(0.12)
    assert c.count_done > snap, "resumed clicker must click again"
    assert not c.paused
    c.stop(); c.wait_done(1.0)
    assert not c.running
    print(f"[8] pause/resume OK (clicked {n1} -> paused {snap} -> resumed {c.count_done})")
finally:
    core.send_click = orig_click

# 9) 真实按住→自动让路→松手恢复（打桩，驱动 App 方法）
if HEADLESS:
    print("[9] skipped (headless CI)")
else:
    ev = []
    orig_sc = core.send_click
    core.send_click = lambda button="left", pos=None: ev.append(("click", button))
    try:
        root = tk.Tk()
        a = appmod.App(root)
        root.update()
        time.sleep(0.25)
        # 关真钩子/热键，直接驱动方法
        if a.hook:
            a.hook.stop(); time.sleep(0.12); a.hook = None
        if a.listener:
            a.listener.stop(); time.sleep(0.12); a.listener = None
        a.interval_var.set("20")
        a.limit_var.set(False)
        a.mode_var.set("follow")
        a.yield_var.set(True)

        def flush():
            a.clicker.wait_done(1.0)
            root.update()

        # 开始连点
        a.toggle()
        assert a.clicker.running and a.clicker.mode == "click"
        time.sleep(0.1)
        assert ("click", "left") in ev
        # 真实按住左键 -> 连点自动暂停（不吞、不发任何注入事件）
        n_before = len(ev)
        a._real_down("left")
        assert a.clicker.paused, "real hold must pause running clicker"
        assert a._resume_after_hold and "left" in a._held
        time.sleep(0.08)
        snap = a.clicker.count_done
        time.sleep(0.08)
        assert a.clicker.count_done == snap, "no clicks while user holds"
        # 暂停瞬间至多 1 发已过检查的在途点击；按住期间必须零新增
        assert len(ev) <= n_before + 1, "yield must not inject extra events"
        # 松手 -> 自动恢复
        a._real_up("left")
        assert not a.clicker.paused and not a._held
        assert a.clicker.running
        time.sleep(0.1)
        assert a.clicker.count_done > snap, "clicks resume after release"
        print("[9] hold->yield->release->resume OK")

        # 多键同按：左+右都按着，松左仍让路，松右才恢复
        a._real_down("left")
        a._real_down("right")
        assert a.clicker.paused
        a._real_up("left")
        assert a.clicker.paused, "still holding right, must stay paused"
        a._real_up("right")
        assert not a.clicker.paused
        print("[9] multi-button hold OK")

        # 按住时启动连点 -> 以暂停态启动，松手自动开点
        a.clicker.stop(); flush()
        a._real_down("left")
        a.toggle()
        assert a.clicker.running and a.clicker.paused, "start while holding must start paused"
        assert a._resume_after_hold
        time.sleep(0.1)
        assert a.clicker.count_done == 0, "no clicks until release"
        a._real_up("left")
        time.sleep(0.1)
        assert not a.clicker.paused and a.clicker.count_done > 0
        a.clicker.stop(); flush()
        print("[9] start-while-holding OK")

        # 关掉让路 -> 按住不再暂停
        a.yield_var.set(False)
        a.toggle()
        time.sleep(0.06)
        a._real_down("left")
        assert not a.clicker.paused, "yield off: hold must not pause"
        a._real_up("left")
        a.clicker.stop(); flush()
        # 让路暂停中关掉勾选 -> 立即恢复
        a.yield_var.set(True)
        a.toggle()
        time.sleep(0.06)
        a._real_down("left")
        assert a.clicker.paused
        a.yield_var.set(False)
        a._yield_changed()
        assert not a.clicker.paused, "turning yield off while paused must resume"
        a._real_up("left")
        a.clicker.stop(); flush()
        print("[9] yield toggle OK")

        # 收尾
        close_app(a, root)
    finally:
        core.send_click = orig_sc

print("ALL TESTS PASSED")