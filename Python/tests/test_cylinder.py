import sys,tempfile,unittest,zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from embrace_core import Course,parse_dvh,PlanComparison
from embrace_export import export_workbook

class CylinderTests(unittest.TestCase):
    def test_defaults_and_totals(self):
        c=Course.for_mode('Cylinder')
        self.assertEqual((c.count,c.prescription_gy),(3,7))
        c.prior_fractions=25;c.dose_per_fx=1.8
        for i in range(3):c.edit(i,'ctvhr_D90',7)
        self.assertAlmostEqual(c.total('ctvhr_D90'),29.75)
        self.assertEqual([x[0] for x in c.sections[0][1]],['CTV'])
        self.assertTrue(all(not m.goal and not m.hard for _,_,ms in c.structures for m in ms))
        self.assertAlmostEqual(Course().baseline(10),44.25)
    def test_import_and_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'dvh.txt';p.write_text('Dose [Gy]\nCumulative mode\nROI: CTV_fx1\n0 10\n7 9\n14 0\nROI: Bladder\n0 10\n7 2\n14 0\n')
            c=Course.for_mode('Cylinder');c.load(0,p)
            self.assertEqual(c.values[0]['ctvhr_D90'],7)
            self.assertNotIn('ctvhr',parse_dvh(p,7).curves)
            plans=PlanComparison();plans.load(0,p,c)
            self.assertAlmostEqual(plans.scenario(0,c).total('ctvhr_D90'),29.75)
            out=Path(tmp)/'cylinder.xlsx';export_workbook(c,'unused',out)
            with zipfile.ZipFile(out) as z:
                xml=z.read('xl/worksheets/sheet1.xml').decode()
                self.assertIn('PORTEC-4',xml);self.assertNotIn('EBRT',xml)
                self.assertIn('29.75',xml);self.assertIn('>CTV<',xml)
