import ctypes
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
import core
import app


class KeyboardHotkeyTests(unittest.TestCase):
    def test_mapping_keeps_old_settings_and_accepts_any_vk(self):
        self.assertEqual(core.hotkey_vk('F8'), 0x77)
        self.assertEqual(core.hotkey_vk('VK:65'), 0x41)
        self.assertIsNone(core.hotkey_vk('VK:999'))
        self.assertIsNone(core.hotkey_vk('broken'))

    def test_key_passes_through_and_only_fires_once_until_released(self):
        fired = []
        listener = core.KeyboardHotkeyListener(0x41, lambda: fired.append('toggle'))
        event = core.KBDLLHOOKSTRUCT()
        event.vkCode = 0x41
        address = ctypes.addressof(event)
        self.assertNotEqual(listener._keyboard_proc(0, core.WM_KEYDOWN, address), 1)
        listener._keyboard_proc(0, core.WM_KEYDOWN, address)
        self.assertEqual(fired, ['toggle'])
        listener._keyboard_proc(0, core.WM_KEYUP, address)
        listener._keyboard_proc(0, core.WM_KEYDOWN, address)
        self.assertEqual(fired, ['toggle', 'toggle'])
        listener._keyboard_proc(0, core.WM_KEYUP, address)
        event.flags = core.LLKHF_INJECTED
        listener._keyboard_proc(0, core.WM_KEYDOWN, address)
        self.assertEqual(fired, ['toggle', 'toggle'])

    def test_left_and_right_modifiers_match_generic_key(self):
        fired = []
        listener = core.KeyboardHotkeyListener(0x10, lambda: fired.append(True))
        event = core.KBDLLHOOKSTRUCT()
        event.vkCode = 0xA0
        listener._keyboard_proc(0, core.WM_KEYDOWN, ctypes.addressof(event))
        listener._keyboard_proc(0, core.WM_KEYUP, ctypes.addressof(event))
        self.assertEqual(fired, [True])

    def test_combo_requires_exact_modifiers_and_does_not_consume_input(self):
        fired = []
        listener = core.KeyboardHotkeyListener(0x41, lambda: fired.append(True), modifiers=core.HK_CTRL | core.HK_SHIFT)
        event = core.KBDLLHOOKSTRUCT()
        def send(vk, message):
            event.vkCode = vk
            return listener._keyboard_proc(0, message, ctypes.addressof(event))
        send(0x41, core.WM_KEYDOWN); send(0x41, core.WM_KEYUP)
        send(0xA2, core.WM_KEYDOWN)
        send(0x41, core.WM_KEYDOWN); send(0x41, core.WM_KEYUP)
        self.assertEqual(fired, [])
        send(0xA0, core.WM_KEYDOWN)
        self.assertNotEqual(send(0x41, core.WM_KEYDOWN), 1)
        send(0x41, core.WM_KEYDOWN)
        self.assertEqual(fired, [True])
        send(0x41, core.WM_KEYUP)
        send(0xA0, core.WM_KEYUP)
        send(0x41, core.WM_KEYDOWN)
        self.assertEqual(fired, [True])
        self.assertEqual(core.hotkey_parse('HK:65:5'), (65, 5))
        self.assertEqual(core.hotkey_parse('F8'), (0x77, 0))

    def test_capture_stores_vk_and_preserves_input_outside_capture(self):
        a = app.App.__new__(app.App)
        a._capturing_hotkey = True
        a._hotkey_setting = 'F8'
        a.hotkey_var = Mock()
        a.cfg = {}
        a._register_hotkey = Mock()
        self.assertEqual(a._capture_hotkey(SimpleNamespace(keycode=65)), 'break')
        self.assertEqual(a._hotkey_setting, 'VK:65')
        self.assertEqual(a.cfg['hotkey'], 'VK:65')
        a._register_hotkey.assert_called_once_with('VK:65')
        self.assertIsNone(a._capture_hotkey(SimpleNamespace(keycode=66)))

    def test_capture_combo_and_single_modifier(self):
        a = app.App.__new__(app.App)
        a._capturing_hotkey = True
        a._capture_modifiers = set()
        a._capture_chorded = False
        a.hotkey_var = Mock()
        a.cfg = {}
        a._register_hotkey = Mock()
        a._capture_hotkey(SimpleNamespace(keycode=0x11))
        self.assertTrue(a._capturing_hotkey)
        a._capture_hotkey(SimpleNamespace(keycode=0x10))
        a._capture_hotkey(SimpleNamespace(keycode=0x41))
        self.assertEqual(a.cfg['hotkey'], 'HK:65:5')
        a._capturing_hotkey = True
        a._capture_modifiers = set()
        a._capture_chorded = False
        a._capture_hotkey(SimpleNamespace(keycode=0x11))
        a._capture_hotkey_release(SimpleNamespace(keycode=0x11))
        self.assertEqual(a.cfg['hotkey'], 'VK:17')

    def test_single_modifier_does_not_fire_when_used_in_a_combo(self):
        fired = []
        listener = core.KeyboardHotkeyListener(0x11, lambda: fired.append(True))
        event = core.KBDLLHOOKSTRUCT()
        def send(vk, message):
            event.vkCode = vk
            listener._keyboard_proc(0, message, ctypes.addressof(event))
        send(0xA2, core.WM_KEYDOWN)
        send(0x41, core.WM_KEYDOWN)
        send(0x41, core.WM_KEYUP)
        send(0xA2, core.WM_KEYUP)
        self.assertEqual(fired, [])


if __name__ == '__main__':
    unittest.main()
