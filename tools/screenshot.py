# -*- coding: utf-8 -*-
"""给 README 截深浅两套主题界面图（只渲染窗口、抓窗口区域，不动鼠标不发点击）。
产物：assets/screenshot-light.png、assets/screenshot-dark.png
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "src")
ASSETS = os.path.join(ROOT, "assets")
os.chdir(SRC)
sys.path.insert(0, SRC)

import tempfile
import tkinter as tk
from PIL import ImageGrab
import app as appmod

appmod.CONFIG_PATH = os.path.join(tempfile.gettempdir(), "whale_clicker_shot_config.json")

root = tk.Tk()
a = appmod.App(root)
# 关掉真钩子/热键，纯截图零干扰
if a.hook:
    a.hook.stop(); time.sleep(0.15); a.hook = None
if a.listener:
    a.listener.stop(); time.sleep(0.15); a.listener = None
root.update_idletasks()
root.update()
time.sleep(0.4)


def shot(name):
    root.update_idletasks()
    root.update()
    time.sleep(0.35)
    x = root.winfo_rootx()
    y = root.winfo_rooty()
    w = root.winfo_width()
    h = root.winfo_height()
    img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
    out = os.path.join(ASSETS, name)
    img.save(out)
    print(f"{name}: {img.size} -> {out}")


for theme, fname in (("light", "screenshot-light.png"), ("dark", "screenshot-dark.png")):
    if a.theme != theme:
        a._toggle_theme()
    shot(fname)

a._on_close()
try:
    root.update()
except Exception:
    pass
try:
    root.destroy()
except Exception:
    pass
print("screenshots done")