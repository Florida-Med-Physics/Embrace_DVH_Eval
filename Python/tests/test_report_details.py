import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tempfile
import unittest
from embrace_core import Course,parse_dvh,file_creation_date
from embrace_dvh_report import relative_rows,metric_rows

class ReportDetailsTests(unittest.TestCase):
    def test_absolute_and_relative_curves_and_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'synthetic.txt'
            path.write_text('Dose [Gy]\nVolume [cc]\nCumulative mode\nROI: CTV_HR\n0 10\n5 9\n10 0\n')
            parsed=parse_dvh(path,5)
            self.assertEqual(relative_rows(parsed.curves['ctvhr'],5),[(0,100),(100,90),(200,0)])
            self.assertEqual(relative_rows(parsed.curves['ctvhr'],10)[1],(50,90))
            d90=next(r for r in metric_rows(parsed,5) if r[1]=='D90 [Gy]')
            self.assertEqual(d90[2:],(100,500,90,9))
            path.write_text('Dose [%]\nVolume [%]\nCumulative mode\nROI: CTV_HR\nVolume [cc]: 10\n0 100\n100 90\n200 0\n')
            relative=parse_dvh(path,5)
            self.assertEqual(relative_rows(relative.curves['ctvhr'],10),[(0,100),(100,90),(200,0)])
            self.assertEqual(next(r for r in metric_rows(relative,10) if r[1]=='D90 [Gy]')[3],1000)
    def test_fraction_provenance_and_reset(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'synthetic.txt';path.write_text('Dose [Gy]\nCumulative mode\nROI: Bladder\n0 10\n5 2\n10 0\n')
            c=Course();c.load(0,path)
            self.assertIsNotNone(c.dvhs[0]);self.assertIsNone(c.dvhs[1])
            c.modalities[3]='CT';c.screenshots[3]=b'image';c.dvhs[3]=c.dvhs[0]
            c.set_count(3)
            self.assertEqual(c.modalities[3],'MRI + CT');self.assertIsNone(c.screenshots[3]);self.assertIsNone(c.dvhs[3])
            c.screenshots[0]=b'image';c.load(0,path);self.assertIsNone(c.screenshots[0])

    def test_txt_source_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'source.txt'
            body='Dose [Gy]\nCumulative mode\nROI: Bladder\n0 10\n5 2\n10 0\n'
            path.write_text('Date: 2026-09-25\n'+body)
            self.assertEqual(parse_dvh(path).source_date,file_creation_date(path))
            path.write_text(body)
            self.assertEqual(parse_dvh(path).source_date,file_creation_date(path))

    def test_seven_gy_normalization_and_physical_dose_preservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'source.txt'
            path.write_text('Dose [cGy]\nCumulative mode\nROI: CTV_HR\n0 10\n700 9\n1400 0\n')
            parsed=parse_dvh(path,7)
            self.assertEqual(relative_rows(parsed.curves['ctvhr'],7)[1],(100,90))
            first=next(r for r in metric_rows(parsed,7) if r[1]=='D90 [Gy]')
            changed=next(r for r in metric_rows(parsed,14) if r[1]=='D90 [Gy]')
            self.assertEqual(first[2:4],(100,700))
            self.assertEqual(changed[2:4],(50,700))

    def test_creation_time_platform_semantics(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from datetime import datetime
        stamp=1700000000
        expected=datetime.fromtimestamp(stamp).date().isoformat()
        with patch('embrace_core.Path.stat',return_value=SimpleNamespace(st_birthtime=stamp,st_ctime=stamp+86400)):
            self.assertEqual(file_creation_date('sample.txt'),expected)
        with patch('embrace_core.Path.stat',return_value=SimpleNamespace(st_ctime=stamp)):
            with patch('embrace_core.os.name','nt'):
                self.assertEqual(file_creation_date('sample.txt'),expected)
            with patch('embrace_core.os.name','posix'):
                self.assertEqual(file_creation_date('sample.txt'),'')
