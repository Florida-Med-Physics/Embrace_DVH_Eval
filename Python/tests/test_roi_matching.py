import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tempfile
import unittest
from embrace_core import structure_key,parse_dvh

class ROIMatchingTests(unittest.TestCase):
    def test_aliases(self):
        for key,names in {
            'ctvhr':['CTVHR','CTV_HR_fx1','HR-CTV','High Risk CTV Fraction 2'],
            'ctvir':['IR_CTV','CTV intermediate risk','CTVIR'],
            'gtvres':['Residual GTV','GTVres'],
            'bladder':['Blader_fx1','BLADDER'],
            'rectum':['Rectun','Rectum'],
            'sigmoid':['Colon_Sigmoid_fx1','Sigmod'],
            'bowel':['Small bowel','Intestines']}.items():
            for name in names:
                with self.subTest(name=name):self.assertEqual(structure_key(name),key)
        for name in ['CTV','CTVXR','Implant','CTVHR_CTVIR']:
            self.assertIsNone(structure_key(name))
    def test_aliases_reach_curves_and_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'dvh.txt'
            path.write_text('Dose [Gy]\nCumulative mode\n'+''.join(
                f'roi: {name}\n0 10\n7 9\n14 0\n' for name in ['HR-CTV','IR-CTV','Blader','Residual GTV']))
            parsed=parse_dvh(path,7)
            self.assertEqual(set(parsed.curves),{'ctvhr','ctvir','bladder','gtvres'})
            self.assertEqual(parsed.curves['ctvhr']['name'],'HR-CTV')
            self.assertEqual(parsed.metrics['ctvhr_D90'],7)
