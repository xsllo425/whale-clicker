# -*- coding: utf-8 -*-
"""
鲸鱼连点器 · 核心引擎（纯标准库，无第三方依赖）
- SendInput 发送鼠标点击（左/右/中键）
- RegisterHotKey 注册全局热键（默认 F8），独立线程消息泵
- 高精度定时循环，支持固定坐标 / 跟随光标
仅支持 Windows。
"""
import ctypes
import time
import threading
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
winmm = ctypes.WinDLL("winmm")

ULONG_PTR = ctypes.c_size_t

# ---- SendInput 结构体（64 位安全）----
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]

class _INPUTunion(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT)]

class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTunion)]

user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = wintypes.UINT

class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
user32.GetCursorPos.restype = wintypes.BOOL

# ---- 常量 ----
INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_ABSOLUTE = 0x8000

SM_CXSCREEN = 0
SM_CYSCREEN = 1

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
MOD_NOREPEAT = 0x4000

BUTTON_FLAGS = {
    "left": (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
    "right": (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
    "middle": (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP),
}

# 热键名 -> 虚拟键码
VK_BY_NAME = {
    "F1": 0x70, "F2": 0x71, "F3": 0x72, "F4": 0x73,
    "F5": 0x74, "F6": 0x75, "F7": 0x76, "F8": 0x77,
    "F9": 0x78, "F10": 0x79, "F11": 0x7A, "F12": 0x7B,
    "F13": 0x7C, "F14": 0x7D, "F15": 0x7E, "F16": 0x7F,
    "F17": 0x80, "F18": 0x81, "F19": 0x82, "F20": 0x83,
    "F21": 0x84, "F22": 0x85, "F23": 0x86, "F24": 0x87,
}


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", ctypes.c_size_t),
        ("lParam", ctypes.c_ssize_t),
        ("time", wintypes.DWORD),
        ("pt", POINT),
    ]

user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
user32.RegisterHotKey.restype = wintypes.BOOL
user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
user32.UnregisterHotKey.restype = wintypes.BOOL
user32.GetMessageW.argtypes = [ctypes.POINTER(MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.GetMessageW.restype = wintypes.BOOL
user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, ctypes.c_size_t, ctypes.c_ssize_t]
user32.PostThreadMessageW.restype = wintypes.BOOL
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.GetCurrentThreadId.restype = wintypes.DWORD


def get_cursor_pos():
    p = POINT()
    user32.GetCursorPos(ctypes.byref(p))
    return p.x, p.y


def is_elevated():
    """当前进程是否管理员权限。非管理员时，SendInput 无法进入管理员窗口（UIPI）。"""
    try:
        advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        TOKEN_QUERY = 0x0008
        TokenElevation = 20

        class TOKEN_ELEVATION(ctypes.Structure):
            _fields_ = [("TokenIsElevated", wintypes.DWORD)]

        tok = wintypes.HANDLE()
        if not advapi32.OpenProcessToken(k32.GetCurrentProcess(), TOKEN_QUERY, ctypes.byref(tok)):
            return False
        try:
            elev = TOKEN_ELEVATION()
            ret = wintypes.DWORD()
            ok = advapi32.GetTokenInformation(tok, TokenElevation, ctypes.byref(elev),
                                              ctypes.sizeof(elev), ctypes.byref(ret))
            return bool(ok and elev.TokenIsElevated)
        finally:
            k32.CloseHandle(tok)
    except Exception:
        return False


def _make_input(flags, dx=0, dy=0):
    inp = INPUT()
    inp.type = INPUT_MOUSE
    inp.u.mi.dx = dx
    inp.u.mi.dy = dy
    inp.u.mi.mouseData = 0
    inp.u.mi.dwFlags = flags
    inp.u.mi.time = 0
    inp.u.mi.dwExtraInfo = 0
    return inp


def send_click(button="left", pos=None):
    """发送一次完整点击（按下+抬起）。pos 为 (x,y) 屏幕坐标则先绝对定位。"""
    down, up = BUTTON_FLAGS[button]
    if pos is not None:
        sx = user32.GetSystemMetrics(SM_CXSCREEN)
        sy = user32.GetSystemMetrics(SM_CYSCREEN)
        nx = int((pos[0] + 0.5) * 65535 / max(sx, 1))
        ny = int((pos[1] + 0.5) * 65535 / max(sy, 1))
        arr = (INPUT * 3)(
            _make_input(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, nx, ny),
            _make_input(down),
            _make_input(up),
        )
    else:
        arr = (INPUT * 2)(_make_input(down), _make_input(up))
    user32.SendInput(len(arr), arr, ctypes.sizeof(INPUT))


def send_button(button="left", down=True, pos=None):
    """发送单个按下/抬起事件（长按用）。pos 为 (x,y) 屏幕坐标则先绝对定位。"""
    d, u = BUTTON_FLAGS[button]
    flags = d if down else u
    if pos is not None:
        sx = user32.GetSystemMetrics(SM_CXSCREEN)
        sy = user32.GetSystemMetrics(SM_CYSCREEN)
        nx = int((pos[0] + 0.5) * 65535 / max(sx, 1))
        ny = int((pos[1] + 0.5) * 65535 / max(sy, 1))
        arr = (INPUT * 2)(
            _make_input(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, nx, ny),
            _make_input(flags),
        )
    else:
        arr = (INPUT * 1)(_make_input(flags))
    user32.SendInput(len(arr), arr, ctypes.sizeof(INPUT))


class HotkeyListener:
    """在独立线程用 RegisterHotKey + 消息泵监听全局热键。"""

    def __init__(self, vk, callback, hotkey_id=1):
        self.vk = vk
        self.callback = callback
        self.hotkey_id = hotkey_id
        self._thread = None
        self._tid = None
        self.registered = False
        self.error = None

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        self._tid = kernel32.GetCurrentThreadId()
        ok = user32.RegisterHotKey(None, self.hotkey_id, MOD_NOREPEAT, self.vk)
        if not ok:
            self.error = ctypes.get_last_error()
            self.registered = False
            return
        self.registered = True
        msg = MSG()
        while True:
            ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret == 0 or ret == -1:  # WM_QUIT 或错误
                break
            if msg.message == WM_HOTKEY and msg.wParam == self.hotkey_id:
                try:
                    self.callback()
                except Exception:
                    pass
        user32.UnregisterHotKey(None, self.hotkey_id)
        self.registered = False

    def stop(self):
        if self._tid is not None:
            user32.PostThreadMessageW(self._tid, WM_QUIT, 0, 0)


# ---- 全局低级鼠标钩子（侧键开关 + 真实按键按下/松开上报）----
WH_MOUSE_LL = 14
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208
WM_XBUTTONDOWN = 0x020B
WM_XBUTTONUP = 0x020C
XBUTTON1 = 0x0001
XBUTTON2 = 0x0002
LLMHF_INJECTED = 0x01

# 左/右/中键 按下/松开 消息 -> (按键名, 是否按下)
MOUSE_BUTTON_MSG = {
    WM_LBUTTONDOWN: ("left", True),
    WM_LBUTTONUP: ("left", False),
    WM_RBUTTONDOWN: ("right", True),
    WM_RBUTTONUP: ("right", False),
    WM_MBUTTONDOWN: ("middle", True),
    WM_MBUTTONUP: ("middle", False),
}


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", POINT),
        ("mouseData", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
user32.SetWindowsHookExW.restype = wintypes.HHOOK
user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
user32.UnhookWindowsHookEx.restype = wintypes.BOOL
user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
user32.CallNextHookEx.restype = ctypes.c_ssize_t


class InputHookListener:
    """全局低级鼠标钩子线程（只观察，不拦截真实按键）。

    - 侧键1（后退键）按下：触发 on_side1（连点开/关）；swallow_side=True 时吞掉，
      避免同时触发浏览器后退等原功能。侧键2 不再使用，原样放行。
    - 真实左/右/中键按下/松开：触发 on_button_down(button) / on_button_up(button)，
      一律放行（游戏要收到你真实的按住蓄力）。
    - 本程序 SendInput 注入的事件带 LLMHF_INJECTED 标记，直接忽略，
      避免连点器自己的点击触发「暂停」。
    回调在钩子线程触发，调用方自行切回主线程。
    """

    def __init__(self, on_side1=None, on_button_down=None, on_button_up=None,
                 swallow_side=True, side_enabled=True):
        self.on_side1 = on_side1
        self.on_button_down = on_button_down
        self.on_button_up = on_button_up
        self.swallow_side = swallow_side
        self.side_enabled = side_enabled
        self.installed = False
        self.error = None
        self._thread = None
        self._tid = None
        self._hh_mouse = None
        # 必须保留回调对象引用，防止被 GC 回收导致钩子崩溃
        self._mouse_proc_ref = HOOKPROC(self._mouse_proc)

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _fire(self, cb, *args):
        if cb:
            try:
                cb(*args)
            except Exception:
                pass

    def _mouse_proc(self, nCode, wParam, lParam):
        if nCode >= 0:
            info = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
            if not (info.flags & LLMHF_INJECTED):
                if wParam in (WM_XBUTTONDOWN, WM_XBUTTONUP):
                    xbtn = (info.mouseData >> 16) & 0xFFFF
                    if xbtn == XBUTTON1 and self.side_enabled:
                        if wParam == WM_XBUTTONDOWN:
                            self._fire(self.on_side1)
                        if self.swallow_side:
                            return 1
                elif wParam in MOUSE_BUTTON_MSG:
                    button, down = MOUSE_BUTTON_MSG[wParam]
                    if down:
                        self._fire(self.on_button_down, button)
                    else:
                        self._fire(self.on_button_up, button)
                    # 真实按键一律放行，不吞
        return user32.CallNextHookEx(None, nCode, wParam, lParam)

    def _run(self):
        self._tid = kernel32.GetCurrentThreadId()
        self._hh_mouse = user32.SetWindowsHookExW(WH_MOUSE_LL, self._mouse_proc_ref, None, 0)
        if not self._hh_mouse:
            self.error = ctypes.get_last_error()
            return
        self.installed = True
        msg = MSG()
        while True:
            ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret == 0 or ret == -1:  # WM_QUIT 或错误
                break
        user32.UnhookWindowsHookEx(self._hh_mouse)
        self._hh_mouse = None
        self.installed = False

    def stop(self):
        if self._tid is not None:
            user32.PostThreadMessageW(self._tid, WM_QUIT, 0, 0)


class Clicker:
    """连点状态机。start/stop 线程安全，点击在独立工作线程执行。"""

    def __init__(self):
        self.running = False
        self.count_done = 0
        self._worker = None
        self._stop_event = threading.Event()
        self._paused = False
        self._lock = threading.Lock()
        self._timer_on = False
        # 运行中会被读取的参数
        self.interval = 0.1
        self.button = "left"
        self.fixed_pos = None  # None=跟随光标, (x,y)=固定坐标
        self.max_count = 0     # 0=无限
        self.double = False
        self.mode = "click"    # click=连点, hold=长按
        self.hold_duration = 0.0
        self.on_stop = None    # 结束回调（自然结束或手动停止都会触发）

    def start(self, interval, button, fixed_pos, max_count, double=False, start_paused=False):
        with self._lock:
            if self.running:
                return False
            self.interval = max(0.001, float(interval))
            self.button = button if button in BUTTON_FLAGS else "left"
            self.fixed_pos = fixed_pos
            self.max_count = max(0, int(max_count))
            self.double = bool(double)
            self.mode = "click"
            self.count_done = 0
            self._stop_event.clear()
            self._paused = bool(start_paused)
            self.running = True
            winmm.timeBeginPeriod(1)
            self._timer_on = True
            self._worker = threading.Thread(target=self._loop, daemon=True)
            self._worker.start()
            return True

    def stop(self):
        with self._lock:
            if not self.running:
                return
            self._stop_event.set()

    def pause(self):
        """暂停连点（长按期间用）。resume() 恢复，计数与参数保持不变。"""
        self._paused = True

    def resume(self):
        self._paused = False

    @property
    def paused(self):
        return self._paused

    def wait_done(self, timeout=1.0):
        """等待工作线程收尾（确保长按的「抬起」已发出）。"""
        w = self._worker
        if w is not None and w.is_alive():
            w.join(timeout)

    def start_hold(self, button, fixed_pos, duration=0.0):
        """长按模式：按下不松。duration 秒后自动松开；0=一直按住直到 stop()。"""
        with self._lock:
            if self.running:
                return False
            self.button = button if button in BUTTON_FLAGS else "left"
            self.fixed_pos = fixed_pos
            self.hold_duration = max(0.0, float(duration))
            self.mode = "hold"
            self.count_done = 0
            self._stop_event.clear()
            self.running = True
            self._worker = threading.Thread(target=self._hold_loop, daemon=True)
            self._worker.start()
            return True

    def _hold_loop(self):
        button = self.button
        fixed = self.fixed_pos
        duration = self.hold_duration
        stop = self._stop_event
        try:
            pos = fixed if fixed is not None else get_cursor_pos()
            send_button(button, True, pos)
            self.count_done = 1
            if duration > 0:
                stop.wait(duration)   # 到时自动松；提前 stop() 则立即松
            else:
                stop.wait()           # 一直按住，直到 stop()
        finally:
            # 无论正常结束、手动停止还是异常，都必须发出「抬起」，避免按键卡住
            try:
                pos = fixed if fixed is not None else get_cursor_pos()
                send_button(button, False, pos)
            finally:
                self._finish()

    def _finish(self):
        self.running = False
        if self._timer_on:
            winmm.timeEndPeriod(1)
            self._timer_on = False
        cb = self.on_stop
        if cb:
            try:
                cb()
            except Exception:
                pass

    def _loop(self):
        interval = self.interval
        button = self.button
        fixed = self.fixed_pos
        max_count = self.max_count
        double = self.double
        stop = self._stop_event
        next_t = time.perf_counter()
        n = 0
        try:
            while not stop.is_set():
                if self._paused:
                    stop.wait(0.05)
                    next_t = time.perf_counter()
                    continue
                pos = fixed if fixed is not None else get_cursor_pos()
                if self._paused:  # 发送前再查一次：让路当轮生效，避免暂停后漏出一发
                    continue
                send_click(button, pos)
                if double and not self._paused:
                    send_click(button, pos)
                n += 1
                self.count_done = n
                if max_count and n >= max_count:
                    break
                next_t += interval
                delay = next_t - time.perf_counter()
                if delay > 0.002:
                    if stop.wait(delay - 0.001):
                        break
                    while time.perf_counter() < next_t and not stop.is_set():
                        pass
                else:
                    next_t = time.perf_counter()
        finally:
            self._finish()


if __name__ == "__main__":
    # 简单自测：在当前光标位置点 5 下左键，间隔 0.3s
    c = Clicker()
    c.start(0.3, "left", None, 5)
    while c.running:
        time.sleep(0.05)
    print("done, clicks =", c.count_done)