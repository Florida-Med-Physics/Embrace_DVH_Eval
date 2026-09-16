import copy
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
import xml.etree.ElementTree as ET
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from embrace_core import Course, METRICS, parse_dvh, dose_at_volume, eqd2, meets, status
from embrace_export import export_workbook, sheet_paths, NS

SAMPLE = '''Patient: Synthetic QA
Patient Id: TEST-001
Plan: Plan A
Absolute Dose - [cGy]
Cumulative mode
ROI: CTV_HR_fx1
1 0 10
2 500 9
3 1000 0
ROI: Bladder
1 0 20
2 500 2
3 1000 0
'''

class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.file = Path(self.tmp.name)/'synthetic.txt'
        self.file.write_text(SAMPLE)

    def test_units_metrics(self):
        d = parse_dvh(self.file)
        self.assertEqual(d.metrics['ctvhr_D90'], 5)
        self.assertEqual(d.metrics['ctvhr_D98'], 1)
        self.assertEqual(d.metrics['bladder_D2'], 5)
        self.assertEqual(d.metrics['bladder_D0p1'], 9.75)
        self.file.write_text(SAMPLE.replace('[cGy]', '[Gy]').replace('500 ', '5 ').replace('1000 ', '10 '))
        self.assertEqual(parse_dvh(self.file).metrics, d.metrics)

    def test_interpolation_edges(self):
        self.assertEqual(dose_at_volume([(4,2),(6,1)], 3), 4)
        self.assertEqual(dose_at_volume([(4,2),(6,1)], .1), 6)
        self.assertEqual(dose_at_volume([(4,2),(6,2),(8,1)], 2), 4)
        self.assertEqual(dose_at_volume([(6,1),(4,2)], 1.5), 5)

    def test_bad_input(self):
        for text in (SAMPLE.replace('[cGy]','[%]'), SAMPLE.replace('Cumulative mode','Differential mode'), SAMPLE.replace('CTV_HR','Unknown').replace('Bladder','Unknown'), SAMPLE+'\nVolume - [%]'):
            self.file.write_text(text)
            with self.assertRaises(ValueError): parse_dvh(self.file)

    def test_protected_carry(self):
        c = Course()
        c.load(2,self.file)
        c.edit(2,'ctvhr_D90',7)
        c.load(0,self.file)
        self.assertEqual([v['ctvhr_D90'] for v in c.values[:4]], [5,5,7,5])
        c.set_count(5)
        self.assertEqual(c.values[4]['ctvhr_D90'],7)
        c.set_count(3)
        self.assertEqual(c.values[3:], [{},{}])
        self.assertFalse(c.explicit[3])
        c.edit(0,'ctvhr_D90',8)
        self.assertEqual(c.values[1]['ctvhr_D90'],5)

    def test_patient_mismatch_is_atomic(self):
        c = Course()
        c.load(0,self.file)
        before = copy.deepcopy(c)
        self.file.write_text(SAMPLE.replace('TEST-001','TEST-002'))
        with self.assertRaises(ValueError): c.load(1,self.file)
        self.assertEqual(c,before)

    def test_eqd2_prior_and_rounding(self):
        c = Course()
        self.assertAlmostEqual(c.baseline(10),44.25)
        self.assertAlmostEqual(c.baseline(3),43.2)
        self.assertIsNone(c.total('ctvhr_D90'))
        c.edit(0,'ctvhr_D90','7.126')
        self.assertEqual(c.values[0]['ctvhr_D90'],7.13)
        self.assertAlmostEqual(c.total('ctvhr_D90'),44.25+7.13*(1+7.13/10)/1.2)
        c.set_prior(2,20.5)
        self.assertEqual(c.prior_fractions,21)
        self.assertEqual(c.baseline(10),42)
        c.edit(0,'ctvhr_D90','')
        self.assertIsNone(c.total('ctvhr_D90'))
        for value in ('nan','inf','abc'):
            with self.assertRaises(ValueError): c.edit(0,'ctvhr_D90',value)
        with self.assertRaises(ValueError): c.set_prior(-1,25)

    def test_constraints(self):
        self.assertFalse(meets(85,'>85'))
        self.assertFalse(meets(80,'<80'))
        self.assertTrue(meets(90,'90-95'))
        self.assertTrue(meets(95,'90-95'))
        m = METRICS['ctvhr_D90']
        self.assertEqual(status(90,m),'pass')
        self.assertEqual(status(96,m),'warn')
        self.assertEqual(status(85,m),'fail')
        self.assertEqual(status(None,m),'neutral')
        self.assertEqual(status(89.999,m),'pass')

    def test_export_template_preserved_and_stale_inputs_cleared(self):
        c = Course(count=3)
        c.load(0,self.file)
        template = Path(__file__).resolve().parents[2]/'Matlab/EQD2_with_tolerances_090126.xlsx'
        original = template.read_bytes()
        output = Path(self.tmp.name)/'out.xlsx'
        names = export_workbook(c,template,output)
        self.assertEqual(len(names),2)
        self.assertEqual(template.read_bytes(),original)
        q = lambda s:'{'+NS+'}'+s
        with zipfile.ZipFile(template) as src, zipfile.ZipFile(output) as dst:
            sheets = sheet_paths(dst)
            for item in src.namelist():
                if item not in sheets.values() and item != 'xl/workbook.xml':
                    self.assertEqual(src.read(item),dst.read(item),item)
            for path in sheets.values():
                root = ET.fromstring(dst.read(path))
                cells = {v.get('r'):v for v in root.iter(q('c'))}
                self.assertEqual(float(cells['C45'].find(q('v')).text),5)
                self.assertEqual(cells['C3'].find(q('is')).find(q('t')).text,'Synthetic QA    MRN: TEST-001')
                for ref in ('F45','G45','H45','C39','D39'):
                    self.assertEqual(len(cells[ref]),0,ref)
                self.assertIsNotNone(cells['C46'].find(q('f')))
                self.assertIsNone(cells['C46'].find(q('v')))
                old = ET.fromstring(src.read(path))
                old_cells = {v.get('r'):v for v in old.iter(q('c'))}
                physical = {col+str(m.row) for m in METRICS.values() for col in 'CDEFGH'}
                for ref,cell in old_cells.items():
                    if ref not in physical:
                        f = cell.find(q('f'))
                        if f is not None:
                            self.assertEqual(ET.tostring(f), ET.tostring(cells[ref].find(q('f'))))
            self.assertIn(b'fullCalcOnLoad="1"',dst.read('xl/workbook.xml'))
        with self.assertRaises(ValueError): export_workbook(c,template,template)
        with self.assertRaises(ValueError): export_workbook(Course(),template,output)

if __name__ == '__main__': unittest.main()
