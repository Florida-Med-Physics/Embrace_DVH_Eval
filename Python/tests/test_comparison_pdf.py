import copy
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from embrace_core import Course, PlanComparison, eqd2, fmt
from embrace_pdf import export_pdf, export_comparison_pdf
from test_dashboard import SAMPLE


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'plan.txt'
        self.path.write_text(SAMPLE)
        self.course=Course()
        self.plans=PlanComparison()

    def test_three_four_five_fraction_totals(self):
        self.plans.load(0,self.path,self.course)
        for n in (3,4,5):
            self.course.set_count(n)
            result=self.plans.scenario(0,self.course)
            self.assertAlmostEqual(result.total('ctvhr_D90'),44.25+n*6.25)
            self.assertAlmostEqual(result.total('bladder_D2'),43.2+n*8)
        self.course.set_prior(2,20)
        self.assertAlmostEqual(self.plans.scenario(0,self.course).total('ctvhr_D90'),40+5*6.25)

    def test_four_independent_plans_and_clear(self):
        for slot in range(4):
            self.path.write_text(SAMPLE.replace('500 ',str(500+slot*100)+' '))
            self.plans.load(slot,self.path,self.course)
        self.assertEqual([p.metrics['ctvhr_D90'] for p in self.plans.plans],[5,6,7,8])
        before=copy.deepcopy(self.course)
        results=[self.plans.scenario(i,self.course) for i in range(4)]
        self.assertEqual(self.course,before)
        self.assertLess(results[0].total('ctvhr_D90'),results[3].total('ctvhr_D90'))
        self.plans.clear(1)
        self.assertIsNone(self.plans.scenario(1,self.course))
        self.assertIsNotNone(self.plans.scenario(0,self.course))

    def test_mismatch_and_reload_are_atomic(self):
        self.plans.load(0,self.path,self.course)
        before=copy.deepcopy(self.plans)
        self.path.write_text(SAMPLE.replace('TEST-001','TEST-002'))
        with self.assertRaises(ValueError): self.plans.load(1,self.path,self.course)
        self.assertEqual(before,self.plans)
        self.course.patient_id='TEST-003'
        with self.assertRaises(ValueError): self.plans.load(2,self.path,self.course)
        self.course.patient_id=''
        self.path.write_text(SAMPLE.split('ROI: Bladder')[0])
        self.plans.load(0,self.path,self.course)
        self.assertNotIn('bladder_D2',self.plans.plans[0].metrics)

    def test_one_decimal_display_keeps_model_precision(self):
        self.course.edit(0,'ctvhr_D90',7.13)
        self.assertEqual(fmt(self.course.values[0]['ctvhr_D90']),'7.1')
        self.assertEqual(self.course.values[0]['ctvhr_D90'],7.13)

    def test_pdf_export_does_not_change_inputs(self):
        self.plans.load(0,self.path,self.course)
        scenario=self.plans.scenario(0,self.course)
        before=copy.deepcopy(scenario)
        for name,fn,args in [('course',export_pdf,(scenario,)),('comparison',export_comparison_pdf,(self.plans,self.course))]:
            output=Path(self.tmp.name)/(name+'.pdf')
            fn(*args,output)
            data=output.read_bytes()
            self.assertTrue(data.startswith(b'%PDF-'))
            self.assertIn(b'%%EOF',data)
        self.assertEqual(before,scenario)
        with self.assertRaises(ValueError): export_pdf(Course(),Path(self.tmp.name)/'empty.pdf')
        with self.assertRaises(ValueError): export_comparison_pdf(PlanComparison(),self.course,Path(self.tmp.name)/'empty.pdf')

if __name__=='__main__': unittest.main()
