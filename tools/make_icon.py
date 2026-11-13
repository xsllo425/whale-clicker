# -*- coding: utf-8 -*-
"""从 assets/whale.png 生成多尺寸 whale.ico（窗口 / exe 图标）。"""
import os
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(os.path.dirname(HERE), "assets")
src = os.path.join(ASSETS, "whale.png")
img = Image.open(src).convert("RGBA")
alpha = img.getchannel("A")
hist = alpha.histogram()
transparent = sum(hist[:250])
total = img.width * img.height
print(f"size={img.size} transparent_px={transparent}/{total} ({100*transparent/total:.1f}%)")
sizes = [16, 24, 32, 48, 64, 128, 256]
img.save(os.path.join(ASSETS, "whale.ico"), sizes=[(s, s) for s in sizes])
print("whale.ico written:", sizes)