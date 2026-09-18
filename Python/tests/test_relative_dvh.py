from pathlib import Path
import copy
import tempfile
import unittest
from embrace_core import Course,PlanComparison,parse_dvh,MissingVolumeError,eqd2


def dvh(dose_unit='Gy',volume_unit='cc',metadata=True,indexed=True):
    dose_scale={'Gy':1,'cGy':100,'%':100/7}[dose_unit]
    pieces=['Patient: Unit Test','Patient Id: U001','Plan: Units',f'Dose - [{dose_unit}]',f'Volume - [{volume_unit}]','Cumulative mode']
    for name,total,rows in [('CTV_HR',10,[(0,10),(7,9),(14,0)]),('Bladder',20,[(0,20),(7,2),(14,0)])]:
        pieces.append('ROI: '+name)
        if metadata: pieces.append(f'Volume [cc]: {total}')
        for i,(d,v) in enumerate(rows,1):
            pieces.append((f'{i} ' if indexed else '')+f'{d*dose_scale:.12g} {v*100/total if volume_unit=="%" else v:.12g}')
    return '\n'.join(pieces)+'\n'


class RelativeDVHTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'dvh.txt'

    def write(self,*args,**kwargs):
        self.path.write_text(dvh(*args,**kwargs));return self.path

    def test_absolute_relative_equivalence_all_combinations(self):
        expected=parse_dvh(self.write()).metrics
        for du in ('Gy','cGy','%'):
            for vu in ('cc','%'):
                for indexed in (True,False):
                    result=parse_dvh(self.write(du,vu,indexed=indexed),7)
                    self.assertEqual(result.metrics,expected,(du,vu,indexed))

    def test_relative_dose_requires_prescription(self):
        with self.assertRaises(ValueError):parse_dvh(self.write('%'))
        for value in (0,-7,float('nan'),float('inf')):
            with self.assertRaises(ValueError):parse_dvh(self.path,value)

    def test_relative_volume_requires_explicit_cc(self):
        self.write('Gy','%',metadata=False)
        with self.assertRaises(MissingVolumeError) as caught:parse_dvh(self.path,7)
        self.assertEqual(caught.exception.names,['CTV_HR','Bladder'])
        result=parse_dvh(self.path,7,{'CTV_HR':10,'Bladder':20})
        self.assertEqual(result.metrics['ctvhr_volume'],10)
        self.assertEqual(result.metrics['bladder_D2'],7)
        with self.assertRaises(ValueError):parse_dvh(self.path,7,{'CTV_HR':0,'Bladder':20})

    def test_prescription_updates_relative_not_absolute(self):
        c=Course()
        self.assertEqual((c.prescription_gy,c.count),(7,4))
        c.load(0,self.write('%'))
        self.assertEqual(c.values[0]['ctvhr_D90'],7)
        c.load(1,self.write('Gy'))
        c.set_prescription(8)
        self.assertEqual(c.values[0]['ctvhr_D90'],8)
        self.assertEqual(c.values[1]['ctvhr_D90'],7)
        self.assertAlmostEqual(c.total('ctvhr_D90'),44.25+eqd2(8,10)+3*eqd2(7,10))
        c.set_prescription(7)
        self.assertEqual(c.values[0]['ctvhr_D90'],7)
        c.edit(0,'ctvhr_D90','90%')
        c.set_prescription(8)
        self.assertEqual(c.values[0]['ctvhr_D90'],7.2)
        c.edit(0,'ctvhr_D90',6)
        c.set_prescription(7)
        self.assertEqual(c.values[0]['ctvhr_D90'],6)

    def test_fraction_regimens_and_no_drift(self):
        c=Course()
        for n,d in [(3,8),(4,7),(5,5)]:
            c.set_count(n);c.set_prescription(d)
            c.load(0,self.write('%'))
            self.assertAlmostEqual(c.total('ctvhr_D90'),44.25+n*d*(d+10)/12)
            self.assertAlmostEqual(c.prescription_eqd2(),n*d*(d+10)/12)
        c.set_count(3);self.assertEqual(c.relative_doses[3:], [{},{}])
        c.set_count(5);self.assertTrue(c.relative_doses[4])
        for _ in range(10):c.set_prescription(8);c.set_prescription(7)
        self.assertEqual(c.values[0]['ctvhr_D90'],7)

    def test_comparison_uses_new_rx_in_all_four_slots(self):
        c=Course();plans=PlanComparison()
        for slot in range(4):plans.load(slot,self.write('%' if slot<2 else 'Gy'),c)
        c.set_prescription(8)
        for slot in range(4):
            scenario=plans.scenario(slot,c)
            dose=8 if slot<2 else 7
            self.assertEqual(scenario.values[0]['ctvhr_D90'],dose)
            self.assertAlmostEqual(scenario.total('ctvhr_D90'),44.25+4*eqd2(dose,10))

    def test_failed_relative_import_does_not_change_course(self):
        c=Course();c.load(0,self.write());before=copy.deepcopy(c)
        with self.assertRaises(MissingVolumeError):c.load(1,self.write('%','%',metadata=False))
        self.assertEqual(c,before)

    def test_unknown_or_ambiguous_units_and_bad_percent_volume(self):
        self.write('%','%')
        for text in [self.path.read_text().replace('1 0 100','1 0 101'),dvh()+'Dose [%]\n',dvh().replace('[Gy]','[unknown]')]:
            self.path.write_text(text)
            with self.assertRaises(ValueError):parse_dvh(self.path,7)

if __name__=='__main__':unittest.main()
