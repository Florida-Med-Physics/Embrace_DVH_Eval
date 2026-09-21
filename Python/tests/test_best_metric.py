import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from embrace_core import best_metric_slots, METRICS

class BestMetricTests(unittest.TestCase):
    def test_goal_matches_tie(self):
        self.assertEqual(best_metric_slots({0:60,1:70,2:85},METRICS['bladder_D2']),[0,1])
    def test_closest_and_range(self):
        self.assertEqual(best_metric_slots({0:86,1:82},METRICS['bladder_D2']),[1])
        self.assertEqual(best_metric_slots({0:89,1:97},METRICS['ctvhr_D90']),[0])
    def test_missing_and_undefined(self):
        self.assertIsNone(best_metric_slots({0:90,1:None},METRICS['ctvhr_D90']))
        self.assertIsNone(best_metric_slots({0:90},METRICS['ctvhr_D90']))
        self.assertIsNone(best_metric_slots({0:90,1:95},METRICS['ctvhr_D50']))
    def test_strict_threshold(self):
        self.assertEqual(best_metric_slots({0:80,1:79},METRICS['bladder_D2']),[1])
