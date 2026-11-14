import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from battle_planner import BattlePlanner, BattleView, CharacterProfile


class BattlePlannerTests(unittest.TestCase):
    def setUp(self):
        self.planner = BattlePlanner({'heart': CharacterProfile(('E', 'R'), attack_interval=0.3)})
        self.planner.start()

    def view(self, **changes):
        values = dict(timestamp=10.0, character='heart', confidence=0.95,
                      focused=True, in_combat=True, user_holding=False,
                      ready_skills=frozenset({'E'}))
        values.update(changes)
        return BattleView(**values)

    def test_requires_consecutive_recognition_and_emits_only_configured_ready_skill(self):
        self.assertIsNone(self.planner.decide(self.view(), 10.0))
        self.assertEqual(self.planner.decide(self.view(timestamp=10.1), 10.1), 'E')
        self.assertIsNone(self.planner.decide(self.view(timestamp=10.1), 10.2))
        self.assertEqual(self.planner.decide(self.view(timestamp=10.5, ready_skills=frozenset()), 10.5), 'attack')

    def test_stops_for_stale_unknown_background_menu_or_physical_hold(self):
        for changes in ({'focused': False}, {'in_combat': False}, {'user_holding': True},
                        {'confidence': 0.4}, {'character': 'unknown'}, {'timestamp': 8.0}):
            self.assertIsNone(self.planner.decide(self.view(**changes), 10.0))
        self.assertIsNone(self.planner.decide(self.view(), 10.0))
        self.planner.stop()
        self.assertIsNone(self.planner.decide(self.view(timestamp=10.1), 10.1))

    def test_switch_resets_confirmation_and_start_resets_state(self):
        self.assertIsNone(self.planner.decide(self.view(), 10.0))
        self.assertIsNone(self.planner.decide(self.view(timestamp=10.1, character='unknown'), 10.1))
        self.assertIsNone(self.planner.decide(self.view(timestamp=10.2), 10.2))
        self.planner.stop()
        self.planner.start()
        self.assertIsNone(self.planner.decide(self.view(timestamp=10.3), 10.3))

    def test_skill_is_not_repeated_until_it_was_observed_unavailable(self):
        self.planner.decide(self.view(), 10.0)
        self.assertEqual(self.planner.decide(self.view(timestamp=10.1), 10.1), 'E')
        self.assertEqual(self.planner.decide(self.view(timestamp=10.5), 10.5), 'attack')
        self.assertEqual(self.planner.decide(self.view(timestamp=10.9, ready_skills=frozenset()), 10.9), 'attack')
        self.assertEqual(self.planner.decide(self.view(timestamp=11.3), 11.3), 'E')


if __name__ == '__main__':
    unittest.main()
