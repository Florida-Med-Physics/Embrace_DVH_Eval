import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from embrace_core import Course, MissingVolumeError

class StructureReviewTests(unittest.TestCase):
    def test_rematch_updates_metrics_curves_and_carried_fractions(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'dvh.txt'
            path.write_text('Dose [Gy]\nVolume [cc]\nCumulative mode\nROI: CTV_HR\n0 10\n5 9\n10 0\nROI: Custom_Target\n0 20\n7 18\n14 0\n')
            c=Course();c.load(0,path);c.load(2,path)
            c.set_fx_date(0,'2026-08-31')
            self.assertEqual(c.dvhs[0].structure_matches,{'CTV_HR':'ctvhr','Custom_Target':None})
            path.unlink()  # Review uses the imported data, even if the TXT moved.
            c.rematch_structures(0,{'CTV_HR':None,'Custom_Target':'ctvhr'})
            self.assertEqual(c.values[0]['ctvhr_D90'],7)
            self.assertEqual(c.values[1]['ctvhr_D90'],7)
            self.assertEqual(c.values[2]['ctvhr_D90'],5)
            self.assertEqual(c.dvhs[0].curves['ctvhr']['name'],'Custom_Target')
            self.assertEqual(c.fx_dates[0],'2026-08-31')
            with self.assertRaises(ValueError):
                c.rematch_structures(0,{'CTV_HR':'ctvhr','Custom_Target':'ctvhr'})
            self.assertEqual(c.values[0]['ctvhr_D90'],7)
            c.rematch_structures(0,{'CTV_HR':None,'Custom_Target':'gtvres'})
            self.assertNotIn('ctvhr_D90',c.values[0])
            self.assertIn('gtvres_D98',c.values[0])
            self.assertNotIn('ctvhr',c.dvhs[0].curves)

    def test_relative_volume_and_dose_remain_correct(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'relative.txt'
            path.write_text('Dose [%]\nVolume [%]\nCumulative mode\nROI: CTV_HR\nVolume [cc]: 10\n0 100\n100 90\n200 0\nROI: Custom\n0 100\n150 90\n200 0\n')
            c=Course();c.load(0,path)
            mapping={'CTV_HR':None,'Custom':'ctvhr'}
            with self.assertRaises(MissingVolumeError):c.rematch_structures(0,mapping)
            c.rematch_structures(0,mapping,{'Custom':20})
            self.assertEqual(c.values[0]['ctvhr_D90'],10.5)
            c.set_prescription(8)
            self.assertEqual(c.values[0]['ctvhr_D90'],12)
            c.rematch_structures(0,mapping)
            self.assertEqual(c.values[0]['ctvhr_D90'],12)

if __name__=='__main__':unittest.main()
