import ctypes
import os
import sys
import unittest
import threading
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
import core


class BattleInputTests(unittest.TestCase):
    def test_keyboard_events_have_correct_key_and_release_flag(self):
        events = []
        def send(count, inputs, size):
            item = inputs[0]
            events.append((count, size, item.type, item.u.ki.wVk, item.u.ki.dwFlags))
            return count
        with patch.object(core.user32, 'SendInput', side_effect=send):
            core.send_key_event(0x45, True)
            core.send_key_event(0x45, False)
        self.assertEqual(events, [(1, ctypes.sizeof(core.INPUT), 1, 0x45, 0),
                                  (1, ctypes.sizeof(core.INPUT), 1, 0x45, 2)])

    def test_invalid_or_failed_input_is_not_silently_accepted(self):
        with patch.object(core.user32, 'SendInput', return_value=0) as send:
            with self.assertRaises(ValueError):
                core.send_key_event(999, True)
            send.assert_not_called()
            with self.assertRaises(OSError):
                core.send_key_event(0x45, True)

    def test_interrupted_hold_always_releases_key(self):
        stop = threading.Event()
        events = []
        def send(vk, down):
            events.append((vk, down))
            if down:
                stop.set()
        with patch.object(core, 'send_key_event', side_effect=send):
            self.assertFalse(core.hold_key_until(0x45, 10, stop))
        self.assertEqual(events, [(0x45, True), (0x45, False)])

    def test_already_stopped_does_not_press_key(self):
        stop = threading.Event()
        stop.set()
        with patch.object(core, 'send_key_event') as send:
            self.assertFalse(core.hold_key_until(0x45, 1, stop))
            send.assert_not_called()


if __name__ == '__main__':
    unittest.main()
