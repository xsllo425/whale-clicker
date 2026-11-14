import os
import queue
import sys
import threading
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
import app


class DispatchTests(unittest.TestCase):
    def test_worker_posts_without_touching_tk_and_main_thread_drains_in_order(self):
        instance = app.App.__new__(app.App)
        instance._closing = False
        instance._event_queue = queue.Queue()
        received = []
        main_thread = threading.get_ident()
        def callback(value):
            received.append((value, threading.get_ident()))
        worker = threading.Thread(target=lambda: (instance._post(callback, 'down'),
                                                  instance._post(callback, 'up')))
        worker.start()
        worker.join(0.5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(received, [])
        instance._drain_events()
        self.assertEqual(received, [('down', main_thread), ('up', main_thread)])
        instance._closing = True
        instance._post(callback, 'late')
        instance._drain_events()
        self.assertEqual(len(received), 2)


if __name__ == '__main__':
    unittest.main()
