# -*- coding: utf-8 -*-
"""鲸鱼连点器 · 图形界面（tkinter + sv-ttk 主题）

零切换：连点器只管狂点，你自己按住鼠标键（蓄力/重击）时它自动让路，
松手自动接着连点。不需要任何「长按模式」。
- 鼠标侧键1 / F8：连点 开/关
- 真实按住左/右/中键：连点自动暂停；松手自动恢复
"""
import json
import os
import sys
import time
import tkinter as tk
from tkinter import ttk, messagebox

import core

# sv-ttk 是唯一运行时依赖（界面主题）；缺失时回退系统原生主题，功能不受影响
try:
    import sv_ttk
    HAS_SVTTK = True
except ImportError:
    sv_ttk = None
    HAS_SVTTK = False

APP_NAME = "鲸鱼连点器"
APP_VERSION = "1.0.1"


def _app_dir():
    """exe 运行时取 exe 所在目录；源码运行时取本文件所在目录。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _asset_dir():
    """素材目录：源码在仓库 assets/；打包后在 onefile 解压目录 _MEIPASS/assets/。"""
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        return os.path.join(base, "assets")
    return os.path.join(os.path.dirname(_app_dir()), "assets")


CONFIG_PATH = os.path.join(_app_dir(), "config.json")

DEFAULTS = {
    "interval_ms": 100,
    "button": "left",
    "mode": "follow",
    "fixed_x": 0,
    "fixed_y": 0,
    "count_limit": False,
    "count": 100,
    "hotkey": "F8",        # 连点 开/关
    "mouse_side": True,    # 侧键1 作为连点开关
    "swallow_side": True,  # 屏蔽侧键原功能（后退）
    "auto_yield": True,    # 真实按住鼠标键时自动暂停连点
    "theme": "light",      # light / dark
}

BUTTON_LABELS = {"左键": "left", "右键": "right", "中键": "middle"}
BUTTON_LABELS_REV = {v: k for k, v in BUTTON_LABELS.items()}
F_KEYS = [f"F{i}" for i in range(1, 13)]

# 深浅两套语义色（状态文字用）
PALETTE = {
    "light": {"ok": "#0a7d32", "warn": "#c0392b", "muted": "#6b7280", "accent": "#1f6feb"},
    "dark": {"ok": "#4ade80", "warn": "#f87171", "muted": "#9ca3af", "accent": "#58a6ff"},
}


class App:
    def __init__(self, root):
        self.root = root
        self.clicker = core.Clicker()
        self.clicker.on_stop = self._on_clicker_stop
        self.listener = None       # F8 连点热键（RegisterHotKey）
        self.hook = None           # 鼠标钩子：侧键1 开关 + 真实按键观察
        self.capture_deadline = 0
        self._closing = False
        self._held = set()                 # 用户真实按住的鼠标键
        self._resume_after_hold = False    # 松手后是否恢复连点
        self.cfg = dict(DEFAULTS)
        self._load_config()
        self.theme = self.cfg.get("theme", "light")
        if self.theme not in PALETTE:
            self.theme = "light"

        root.title(f"{APP_NAME} v{APP_VERSION}")
        root.resizable(False, False)
        root.attributes("-topmost", True)
        self._set_window_icon()
        self._apply_theme(initial=True)
        self._build_ui()
        self._apply_config_to_ui()
        self._register_hotkey(self.cfg["hotkey"])
        self._register_hook()
        self._tick()
        root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------- 主题 ----------
    def _apply_theme(self, initial=False):
        try:
            if HAS_SVTTK:
                sv_ttk.set_theme(self.theme)
            else:
                style = ttk.Style(self.root)
                if "vista" in style.theme_names():
                    style.theme_use("vista")
            style = ttk.Style(self.root)
            style.configure(".", font=("Microsoft YaHei UI", 10))
            style.configure("Title.TLabel", font=("Microsoft YaHei UI", 15, "bold"))
            style.configure("Tagline.TLabel", font=("Microsoft YaHei UI", 9))
            style.configure("Hint.TLabel", font=("Microsoft YaHei UI", 9))
            style.configure("Status.TLabel", font=("Microsoft YaHei UI", 10, "bold"))
            style.configure("Perm.TLabel", font=("Microsoft YaHei UI", 9))
            style.configure("Big.TButton", font=("Microsoft YaHei UI", 11, "bold"), padding=(10, 8))
        except Exception:
            pass
        if not initial:
            self._recolor()

    def _toggle_theme(self):
        self.theme = "dark" if self.theme == "light" else "light"
        self.cfg["theme"] = self.theme
        self._apply_theme()
        self.theme_btn.config(text="🌙 深色" if self.theme == "light" else "☀ 浅色")

    def _recolor(self):
        """主题切换后刷新所有语义色文字。"""
        p = PALETTE[self.theme]
        self.tagline.config(foreground=p["muted"])
        self.hint.config(foreground=p["muted"])
        for w in self._muted_labels:
            w.config(foreground=p["muted"])
        self._status_widget.config(foreground=p["warn"] if self.clicker.running else p["ok"])
        self._perm_label.config(foreground=p["ok"] if core.is_elevated() else p["warn"])
        self.hk_status.config(foreground=p["muted"])
        self.hook_status.config(foreground=p["muted"])

    def _set_window_icon(self):
        ico = os.path.join(_asset_dir(), "whale.ico")
        png = os.path.join(_asset_dir(), "whale.png")
        try:
            if os.path.exists(ico):
                self.root.iconbitmap(ico)
            elif os.path.exists(png):
                self._icon_img = tk.PhotoImage(file=png)
                self.root.iconphoto(True, self._icon_img)
        except Exception:
            pass

    # ---------- 配置 ----------
    def _load_config(self):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k in DEFAULTS:
                if k in data:
                    self.cfg[k] = data[k]
        except Exception:
            pass

    def _save_config(self):
        try:
            self._read_ui_into_config()
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.cfg, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ---------- 界面 ----------
    def _build_ui(self):
        p = PALETTE[self.theme]
        self._muted_labels = []
        main = ttk.Frame(self.root, padding=(18, 14, 18, 12))
        main.grid(sticky="nsew")

        # 头部：标题 + 主题切换
        head = ttk.Frame(main)
        head.grid(row=0, column=0, sticky="ew", pady=(0, 2))
        ttk.Label(head, text=f"🐋 {APP_NAME}", style="Title.TLabel").pack(side="left")
        self.theme_btn = ttk.Button(head, width=8, command=self._toggle_theme,
                                    text="🌙 深色" if self.theme == "light" else "☀ 浅色")
        self.theme_btn.pack(side="right")
        self.tagline = ttk.Label(main, text="你管长按 · 它管连点 · 松手自动接着点",
                                 style="Tagline.TLabel", foreground=p["muted"])
        self.tagline.grid(row=1, column=0, sticky="w", pady=(0, 10))

        pad = {"padx": 2, "pady": 5}

        # 点击间隔
        row = ttk.Frame(main); row.grid(row=2, column=0, sticky="ew", **pad)
        ttk.Label(row, text="点击间隔", width=9).pack(side="left")
        self.interval_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.interval_var, width=9).pack(side="left")
        lbl = ttk.Label(row, text="毫秒（1～600000）", foreground=p["muted"]); lbl.pack(side="left", padx=6)
        self._muted_labels.append(lbl)

        # 鼠标按键
        row = ttk.Frame(main); row.grid(row=3, column=0, sticky="ew", **pad)
        ttk.Label(row, text="鼠标按键", width=9).pack(side="left")
        self.button_var = tk.StringVar()
        ttk.Combobox(row, textvariable=self.button_var, values=list(BUTTON_LABELS),
                     width=6, state="readonly").pack(side="left")
        self.double_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(row, text="每次双击", variable=self.double_var).pack(side="left", padx=12)

        # 点击位置
        row = ttk.Frame(main); row.grid(row=4, column=0, sticky="ew", **pad)
        ttk.Label(row, text="点击位置", width=9).pack(side="left")
        self.mode_var = tk.StringVar(value="follow")
        ttk.Radiobutton(row, text="跟随鼠标", variable=self.mode_var, value="follow",
                        command=self._mode_changed).pack(side="left")
        ttk.Radiobutton(row, text="固定坐标", variable=self.mode_var, value="fixed",
                        command=self._mode_changed).pack(side="left", padx=6)

        row = ttk.Frame(main); row.grid(row=5, column=0, sticky="ew", **pad)
        ttk.Label(row, text="", width=9).pack(side="left")
        self.pos_label = ttk.Label(row, text="X: -    Y: -", width=16)
        self.pos_label.pack(side="left")
        self.capture_btn = ttk.Button(row, text="取坐标(F9)", width=11, command=self._capture_pos)
        self.capture_btn.pack(side="left", padx=6)

        # 点击次数
        row = ttk.Frame(main); row.grid(row=6, column=0, sticky="ew", **pad)
        ttk.Label(row, text="点击次数", width=9).pack(side="left")
        self.limit_var = tk.BooleanVar()
        ttk.Checkbutton(row, text="限定", variable=self.limit_var,
                        command=self._limit_changed).pack(side="left")
        self.count_var = tk.StringVar()
        self.count_entry = ttk.Entry(row, textvariable=self.count_var, width=9)
        self.count_entry.pack(side="left", padx=6)
        lbl = ttk.Label(row, text="次（不勾选=无限，直到再按停止）", foreground=p["muted"])
        lbl.pack(side="left"); self._muted_labels.append(lbl)

        ttk.Separator(main, orient="horizontal").grid(row=7, column=0, sticky="ew", pady=8)

        # 连点热键
        row = ttk.Frame(main); row.grid(row=8, column=0, sticky="ew", **pad)
        ttk.Label(row, text="连点热键", width=9).pack(side="left")
        self.hotkey_var = tk.StringVar()
        hk = ttk.Combobox(row, textvariable=self.hotkey_var, values=F_KEYS, width=6, state="readonly")
        hk.pack(side="left")
        hk.bind("<<ComboboxSelected>>", self._hotkey_changed)
        lbl = ttk.Label(row, text="开/关连点", foreground=p["muted"]); lbl.pack(side="left", padx=6)
        self._muted_labels.append(lbl)
        self.hk_status = ttk.Label(row, text="", foreground=p["muted"])
        self.hk_status.pack(side="left", padx=8)

        # 鼠标侧键开关
        row = ttk.Frame(main); row.grid(row=9, column=0, sticky="ew", **pad)
        ttk.Label(row, text="鼠标侧键", width=9).pack(side="left")
        self.mouse_side_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(row, text="侧键1=连点开关", variable=self.mouse_side_var,
                        command=self._mouse_side_changed).pack(side="left")
        self.swallow_var = tk.BooleanVar(value=True)
        self.swallow_check = ttk.Checkbutton(row, text="屏蔽侧键原功能", variable=self.swallow_var,
                                             command=self._swallow_changed)
        self.swallow_check.pack(side="left", padx=10)
        self.hook_status = ttk.Label(row, text="", foreground=p["muted"])
        self.hook_status.pack(side="left", padx=8)

        # 自动让路（招牌功能，单独一卡）
        card = ttk.LabelFrame(main, text=" 自动让路 · 招牌功能 ", padding=(10, 8))
        card.grid(row=10, column=0, sticky="ew", pady=(6, 4))
        self.yield_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(card, text="我按住鼠标键时暂停连点，松手自动继续",
                        variable=self.yield_var, command=self._yield_changed).pack(anchor="w")
        lbl = ttk.Label(card, text="蓄力/重击直接按住鼠标，连点自动让路，不用切模式",
                        foreground=p["muted"], font=("Microsoft YaHei UI", 9))
        lbl.pack(anchor="w", pady=(2, 0)); self._muted_labels.append(lbl)

        # 控制按钮
        row = ttk.Frame(main); row.grid(row=11, column=0, sticky="ew", pady=(10, 4))
        self.start_btn = ttk.Button(row, text="▶ 开始连点", width=14, style="Big.TButton",
                                    command=self.toggle)
        self.start_btn.pack(side="left")
        ttk.Button(row, text="保存设置", width=10, command=self._save_config).pack(side="left", padx=10)

        # 状态栏
        self.status_var = tk.StringVar(value="就绪")
        self._status_widget = ttk.Label(main, textvariable=self.status_var, foreground=p["ok"],
                                        style="Status.TLabel")
        self._status_widget.grid(row=12, column=0, sticky="w", pady=(6, 2))

        # 权限提示
        if core.is_elevated():
            perm_text, perm_color = "管理员权限 ✓ 可点击游戏等管理员窗口", p["ok"]
        else:
            perm_text, perm_color = ("普通权限：点不进管理员窗口（多数游戏）！"
                                     "请右键「以管理员身份运行」本程序", p["warn"])
        self._perm_label = ttk.Label(main, text=perm_text, foreground=perm_color,
                                     style="Perm.TLabel", wraplength=480)
        self._perm_label.grid(row=13, column=0, sticky="w", pady=(2, 0))

        self.hint = ttk.Label(main, text="普攻交给它狂点 · 要蓄力就自己按住鼠标，松手它接着点",
                              style="Hint.TLabel", foreground=p["muted"])
        self.hint.grid(row=14, column=0, sticky="w", pady=(6, 0))

    def _apply_config_to_ui(self):
        c = self.cfg
        self.interval_var.set(str(c["interval_ms"]))
        self.button_var.set(BUTTON_LABELS_REV.get(c["button"], "左键"))
        self.mode_var.set(c["mode"])
        self.pos_label.config(text=f"X: {c['fixed_x']}    Y: {c['fixed_y']}")
        self.limit_var.set(bool(c["count_limit"]))
        self.count_var.set(str(c["count"]))
        self.hotkey_var.set(c["hotkey"])
        self.mouse_side_var.set(bool(c.get("mouse_side", True)))
        self.swallow_var.set(bool(c.get("swallow_side", True)))
        self.yield_var.set(bool(c.get("auto_yield", True)))
        self._mode_changed()
        self._limit_changed()
        self._mouse_side_changed()

    def _read_ui_into_config(self):
        c = self.cfg
        c["interval_ms"] = self._parse_interval()
        c["button"] = BUTTON_LABELS.get(self.button_var.get(), "left")
        c["mode"] = self.mode_var.get()
        txt = self.pos_label.cget("text")
        try:
            parts = txt.replace("X:", "").replace("Y:", "").split()
            c["fixed_x"], c["fixed_y"] = int(parts[0]), int(parts[1])
        except Exception:
            pass
        c["count_limit"] = bool(self.limit_var.get())
        c["count"] = self._parse_count()
        c["hotkey"] = self.hotkey_var.get()
        c["mouse_side"] = bool(self.mouse_side_var.get())
        c["swallow_side"] = bool(self.swallow_var.get())
        c["auto_yield"] = bool(self.yield_var.get())
        c["theme"] = self.theme

    def _mode_changed(self):
        state = "normal" if self.mode_var.get() == "fixed" else "disabled"
        self.capture_btn.config(state=state)

    def _limit_changed(self):
        state = "normal" if self.limit_var.get() else "disabled"
        self.count_entry.config(state=state)

    def _mouse_side_changed(self):
        state = "normal" if self.mouse_side_var.get() else "disabled"
        self.swallow_check.config(state=state)
        if self.hook:
            self.hook.side_enabled = bool(self.mouse_side_var.get())

    def _swallow_changed(self):
        if self.hook:
            self.hook.swallow_side = bool(self.swallow_var.get())

    def _yield_changed(self):
        # 关掉让路时，若正处于让路暂停，立即恢复
        if not self.yield_var.get() and self._resume_after_hold:
            self._resume_after_hold = False
            if self.clicker.running and self.clicker.paused:
                self.clicker.resume()

    # ---------- 参数校验 ----------
    def _parse_interval(self):
        try:
            v = float(self.interval_var.get())
        except ValueError:
            raise ValueError("点击间隔要填数字（毫秒）")
        if not (1 <= v <= 600000):
            raise ValueError("点击间隔要在 1～600000 毫秒之间")
        return v

    def _parse_count(self):
        try:
            v = int(self.count_var.get())
        except ValueError:
            raise ValueError("点击次数要填整数")
        if v < 1:
            raise ValueError("点击次数至少为 1")
        return v

    def _get_pos(self):
        """当前点击位置：固定坐标返回 (x,y)，跟随鼠标或坐标无效返回 None。"""
        if self.mode_var.get() == "fixed":
            txt = self.pos_label.cget("text")
            try:
                parts = txt.replace("X:", "").replace("Y:", "").split()
                return (int(parts[0]), int(parts[1]))
            except Exception:
                return None
        return None

    # ---------- 取坐标 ----------
    def _capture_pos(self):
        self.mode_var.set("fixed")
        self._mode_changed()
        self.capture_deadline = time.time() + 3.0
        self.status_var.set("3 秒内把鼠标移到目标位置…")

    # ---------- 连点热键（RegisterHotKey） ----------
    def _register_hotkey(self, name):
        if self.listener:
            self.listener.stop()
            self.listener = None
        vk = core.VK_BY_NAME.get(name)
        if vk is None:
            self.hk_status.config(text="未知热键", foreground=PALETTE[self.theme]["warn"])
            return
        self.listener = core.HotkeyListener(vk, self._hotkey_pressed)
        self.listener.start()

    def _hotkey_changed(self, _event=None):
        name = self.hotkey_var.get()
        self._register_hotkey(name)
        self.cfg["hotkey"] = name

    def _hotkey_pressed(self):
        self.root.after(0, self.toggle)

    # ---------- 鼠标钩子（侧键1 开关 + 真实按键观察） ----------
    def _register_hook(self):
        if self.hook:
            self.hook.stop()
            self.hook = None
        self.hook = core.InputHookListener(
            on_side1=lambda: self.root.after(0, self.toggle),
            on_button_down=lambda b: self.root.after(0, self._real_down, b),
            on_button_up=lambda b: self.root.after(0, self._real_up, b),
            swallow_side=bool(self.swallow_var.get()) if hasattr(self, "swallow_var") else bool(self.cfg.get("swallow_side", True)),
            side_enabled=bool(self.mouse_side_var.get()) if hasattr(self, "mouse_side_var") else bool(self.cfg.get("mouse_side", True)),
        )
        self.hook.start()

    # ---------- 连点 开/关 ----------
    def toggle(self):
        if self.clicker.running:
            self.clicker.stop()
            return
        try:
            interval_ms = self._parse_interval()
            count = self._parse_count() if self.limit_var.get() else 0
        except ValueError as e:
            messagebox.showwarning("参数有误", str(e), parent=self.root)
            return
        button = BUTTON_LABELS.get(self.button_var.get(), "left")
        fixed = None
        if self.mode_var.get() == "fixed":
            fixed = self._get_pos()
            if fixed is None:
                messagebox.showwarning("坐标有误", "先点「取坐标」获取固定坐标", parent=self.root)
                return
        # 若此刻正按住鼠标键，连点以暂停态启动，松手后自动接着点
        start_paused = bool(self.yield_var.get() and self._held)
        if start_paused:
            self._resume_after_hold = True
        ok = self.clicker.start(interval_ms / 1000.0, button, fixed, count,
                                double=bool(self.double_var.get()), start_paused=start_paused)
        if ok:
            self.start_btn.config(text="⏹ 停止连点")
            self._status_widget.config(foreground=PALETTE[self.theme]["warn"])
            if not start_paused:
                self.status_var.set("连点中… 再按一次停止")

    # ---------- 真实按住鼠标键：自动让路 ----------
    def _real_down(self, button):
        self._held.add(button)
        if not self.yield_var.get():
            return
        if self.clicker.running and self.clicker.mode == "click" and not self.clicker.paused:
            self._resume_after_hold = True
            self.clicker.pause()
            self.status_var.set("你按住了鼠标 · 连点暂停，松手继续")

    def _real_up(self, button):
        self._held.discard(button)
        if self._held:
            return  # 还有别的键按着，继续让路
        if self._resume_after_hold:
            self._resume_after_hold = False
            if self.clicker.running and self.clicker.paused:
                self.clicker.resume()
                self.status_var.set("已松手 · 连点继续")

    def _on_clicker_stop(self):
        self.root.after(0, self._stopped_ui)

    def _stopped_ui(self):
        self.start_btn.config(text="▶ 开始连点")
        self._resume_after_hold = False
        self.status_var.set(f"已停止 · 共点击 {self.clicker.count_done} 次")
        self._status_widget.config(foreground=PALETTE[self.theme]["ok"])

    # ---------- 周期刷新 ----------
    def _tick(self):
        if self._closing:
            return
        p = PALETTE[self.theme]
        if self.listener:
            if self.listener.registered:
                self.hk_status.config(text="已注册", foreground=p["ok"])
            elif self.listener.error is not None:
                self.hk_status.config(text="被占用，换一个", foreground=p["warn"])
        if self.hook:
            if self.hook.installed:
                self.hook_status.config(text="")
            elif self.hook.error is not None:
                self.hook_status.config(text="钩子失败", foreground=p["warn"])
        # 取坐标倒计时
        if self.capture_deadline:
            remain = self.capture_deadline - time.time()
            if remain <= 0:
                x, y = core.get_cursor_pos()
                self.pos_label.config(text=f"X: {x}    Y: {y}")
                self.capture_deadline = 0
                if not self.clicker.running:
                    self.status_var.set(f"已取坐标 ({x}, {y})")
            else:
                self.status_var.set(f"{remain:.1f} 秒后取鼠标位置…")
        # 运行中状态
        if self.clicker.running:
            if self.clicker.paused:
                self.status_var.set("你按住了鼠标 · 连点暂停，松手继续")
            else:
                self.status_var.set(f"连点中 · 已点击 {self.clicker.count_done} 次")
        self.root.after(100, self._tick)

    def _on_close(self):
        self._closing = True
        self.clicker.stop()
        self.clicker.wait_done(0.5)
        if self.listener:
            self.listener.stop()
        if self.hook:
            self.hook.stop()
        self._save_config()
        self._destroy_after_id = self.root.after(120, self.root.destroy)


def main():
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()