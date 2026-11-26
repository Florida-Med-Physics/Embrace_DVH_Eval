import unittest
import sys
import tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, RTDoseStorage, RTPlanStorage
from embrace_points import suggest_point
from embrace_dicom import read_point_doses
from embrace_core import Course

class PointTests(unittest.TestCase):
    def test_point_carry_matches_fraction_import_pattern(self):
        c=Course()
        def points(dose,target='point_a_left'):
            return [{'target':target,'dose':dose,'name':'AL','group':'A Points'}]
        c.set_points(0,points(4.924310),'2026-08-31')
        self.assertEqual([d['point_a_left'] for d in c.point_doses[:4]],[4.924310]*4)
        self.assertEqual(c.point_sources[:4],[0]*4)
        c.point_records[1][0]['name']='changed'
        self.assertEqual(c.point_records[0][0]['name'],'AL')
        c.set_points(2,points(6.1),'2026-09-02')
        c.set_points(0,points(5.2),'2026-09-01')
        self.assertEqual([d['point_a_left'] for d in c.point_doses[:4]],[5.2,5.2,6.1,5.2])
        c.set_count(5)
        self.assertEqual(c.point_doses[4]['point_a_left'],6.1)
        c.set_points(2,points(6.1,'point_a_right'),'2026-09-02')
        self.assertEqual(c.point_doses[4],{'point_a_right':6.1})
        c.clear_points(0)
        self.assertEqual(c.point_doses[1],{})
        self.assertEqual(c.point_doses[2],{'point_a_right':6.1})
        c.set_count(3)
        self.assertEqual(c.point_doses[3:], [{},{}])
        self.assertEqual(c.point_sources[3:], [None,None])

    def test_manual_points_are_preserved_on_later_import(self):
        c=Course()
        c.set_points(0,[{'target':'point_a_left','dose':4.0}],'2026-08-31')
        from copy import deepcopy
        doses=deepcopy(c.point_doses)
        doses[1]['point_a_left']=7.0
        c.set_report_details(c.ct_dates,doses)
        c.set_points(0,[{'target':'point_a_left','dose':5.0}],'2026-08-31')
        self.assertEqual(c.point_doses[1]['point_a_left'],7.0)
        self.assertEqual(c.point_doses[2]['point_a_left'],5.0)

    def test_aliases_and_ambiguity(self):
        for name in ('PointA_L','AL','A_L','A_Left','Point A left Fx1','Point A Lef'):
            self.assertEqual(suggest_point(name),'point_a_left')
        for name in ('PointA_R','AR','A_R','A_Right'):
            self.assertEqual(suggest_point(name),'point_a_right')
        self.assertEqual(suggest_point('Rectal point'),'rectovaginal')
        self.assertEqual(suggest_point('Bladder point'),'bladder_point')
        self.assertEqual(suggest_point('Left','Vaginal points'),'vaginal_left')
        self.assertEqual(suggest_point('Vaginal_point_R'),'vaginal_right')
        self.assertEqual(suggest_point('Bladder refernce point'),'bladder_point')
        for name in ('P1','P2','Point A','A','Left'):
            self.assertIsNone(suggest_point(name))
        self.assertIsNone(suggest_point('P1','Vaginal points'))
        self.assertIsNone(suggest_point('Point A left right'))

    def test_vaginal_laterality_aliases(self):
        from embrace_points import POINTS
        self.assertNotIn('vaginal',[key for key,*_ in POINTS])
        for side,shorts in (('left',('L','Lt','Left')),('right',('R','Rt','Right'))):
            for stem in ('Vag','Vagina','Vaginal','Vaginal_point'):
                for short in shorts:
                    for separator in ('_',' ','-',''):
                        name=stem+separator+short
                        with self.subTest(name=name):
                            self.assertEqual(suggest_point(name,'VagPoints'),'vaginal_'+side)
                            self.assertEqual(suggest_point(name+' Fx3'),'vaginal_'+side)
            for short in shorts:
                self.assertEqual(suggest_point(short,'VagPoints'),'vaginal_'+side)
        for name in ('Vag','Vaginal point','Vagina point','P1','P2','Vag_L_R','Vag left right'):
            self.assertIsNone(suggest_point(name,'VagPoints'))

    def write(self,path,modality,uid):
        meta=FileMetaDataset();meta.TransferSyntaxUID=ExplicitVRLittleEndian
        meta.MediaStorageSOPClassUID=RTDoseStorage if modality=='RTDOSE' else RTPlanStorage
        meta.MediaStorageSOPInstanceUID=uid
        ds=FileDataset(str(path),{},file_meta=meta,preamble=b'\0'*128)
        ds.SOPClassUID=meta.MediaStorageSOPClassUID;ds.SOPInstanceUID=uid
        ds.Modality=modality;ds.PatientID='QA';ds.FrameOfReferenceUID='1.2.3.4'
        return ds

    def fixture(self,root):
        rd=self.write(root/'rd.dcm','RTDOSE','1.2.3.1')
        rd.ContentDate='20260831';rd.DoseType='PHYSICAL'
        ref=Dataset();ref.ReferencedSOPInstanceUID='1.2.3.2';rd.ReferencedRTPlanSequence=[ref]
        roi=Dataset();roi.ROINumber=1;roi.ROIName='AL';rd.StructureSetROISequence=[roi]
        c=Dataset();c.ContourGeometricType='POINT';c.NumberOfContourPoints=1;c.ContourData=[1,2,3];c.ContourNumber=1
        contour=Dataset();contour.ReferencedROINumber=1;contour.ContourSequence=[c];rd.ROIContourSequence=[contour]
        dose=Dataset();dose.ReferencedROINumber=1;dose.DoseValue=4.924310;dose.DoseUnits='GY'
        block=dose.private_block(0x300b,'NUCLETRON',create=True);block.add_new(0,'IS',4);block.add_new(1,'IS',1)
        rd.RTDoseROISequence=[dose]
        rp=self.write(root/'rp.dcm','RTPLAN','1.2.3.2')
        ss=Dataset();r=Dataset();r.ROINumber=4;r.ROIName='A Points';ss.StructureSetROISequence=[r]
        pc=Dataset();pc.ContourGeometricType='POINT';pc.ContourNumber=1;pc.ContourData=[1,2,3]
        pc.private_block(0x3007,'NUCLETRON',create=True).add_new(0x16,'LO','AL')
        rc=Dataset();rc.ReferencedROINumber=4;rc.ContourSequence=[pc];ss.ROIContourSequence=[rc]
        rp.private_block(0x300f,'NUCLETRON',create=True).add_new(0,'SQ',[ss])
        rd.save_as(root/'rd.dcm',enforce_file_format=True);rp.save_as(root/'rp.dcm',enforce_file_format=True)
        return rd,rp

    def test_import_and_validation(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);rd,rp=self.fixture(root)
            result=read_point_doses(root/'rd.dcm','QA',root/'rp.dcm')
            self.assertEqual(result['date'],'2026-08-31')
            self.assertEqual(result['points'][0]['group'],'A Points')
            self.assertEqual(result['points'][0]['dose'],4.924310)
            with self.assertRaises(ValueError):read_point_doses(root/'rd.dcm','OTHER',root/'rp.dcm')
            rp.SOPInstanceUID='1.2.3.9';rp.save_as(root/'rp.dcm',enforce_file_format=True)
            with self.assertRaises(ValueError):read_point_doses(root/'rd.dcm','QA',root/'rp.dcm')
            rd.RTDoseROISequence[0].DoseUnits='RELATIVE';rd.save_as(root/'rd.dcm',enforce_file_format=True)
            with self.assertRaises(ValueError):read_point_doses(root/'rd.dcm','QA')

    def test_point_precision_and_reset(self):
        c=Course();c.set_report_details(['']*4,[{'point_a_left':4.924310}]+[{}]*3)
        self.assertEqual(c.point_doses[0]['point_a_left'],4.924310)
        c.point_records[3]=[{'name':'AL'}];c.set_count(3)
        self.assertEqual(c.point_records[3],[])
        with self.assertRaises(ValueError):c.set_report_details(['']*3,[{'bladder_point':'nan'}]+[{}]*2)

    def test_unrelated_files_are_ignored(self):
        from embrace_dicom import read_fraction_dicoms
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'notes.txt').write_text('Not a DICOM export')
            unrelated=self.write(root/'rs.dcm','RTSTRUCT','1.2.3.99')
            unrelated.PatientID='OTHER'
            unrelated.save_as(root/'rs.dcm',enforce_file_format=True)
            ignored=[root/'notes.txt',root/'rs.dcm']
            self.assertIsNone(read_fraction_dicoms(ignored,'QA'))
            self.fixture(root)
            expected=read_fraction_dicoms([root/'rp.dcm',root/'rd.dcm'],'QA')
            actual=read_fraction_dicoms(ignored+[root/'rp.dcm',root/'rd.dcm'],'QA')
            self.assertEqual(actual,expected)

    def test_fraction_bundle_ct_and_automatic_points(self):
        from embrace_dicom import read_fraction_dicoms
        from pydicom.uid import CTImageStorage
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);rd,rp=self.fixture(root)
            ct=self.write(root/'ct.dcm','CT','1.2.3.8')
            ct.SOPClassUID=CTImageStorage;ct.file_meta.MediaStorageSOPClassUID=CTImageStorage
            ct.SeriesInstanceUID='1.2.3.10';ct.AcquisitionDate='20260831';ct.SeriesDate='20260830'
            ct.save_as(root/'ct.dcm',enforce_file_format=True)
            paths=[root/'rp.dcm',root/'ct.dcm',root/'rd.dcm']
            result=read_fraction_dicoms(paths,'QA')
            self.assertEqual(result['ct_date'],'2026-08-31')
            self.assertEqual(result['points'][0]['target'],'point_a_left')
            self.assertEqual(result['points'][0]['dose'],4.924310)
            self.assertIsNone(read_fraction_dicoms([root/'ct.dcm'],'QA')['points'])
            with self.assertRaises(ValueError):read_fraction_dicoms(paths,'OTHER')
            ct.FrameOfReferenceUID='1.2.3.99';ct.save_as(root/'ct.dcm',enforce_file_format=True)
            with self.assertRaises(ValueError):read_fraction_dicoms(paths,'QA')
            ct.FrameOfReferenceUID='1.2.3.4';del ct.AcquisitionDate
            ct.save_as(root/'ct.dcm',enforce_file_format=True)
            result=read_fraction_dicoms(paths,'QA')
            self.assertEqual(result['ct_date'],'2026-08-30');self.assertTrue(result['warnings'])
            del ct.SeriesDate;ct.save_as(root/'ct.dcm',enforce_file_format=True)
            with self.assertRaises(ValueError):read_fraction_dicoms(paths,'QA')

    def test_fraction_bundle_conflicting_cts_and_duplicate_points(self):
        from copy import deepcopy
        from embrace_dicom import read_fraction_dicoms
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);rd,rp=self.fixture(root)
            for i,date in enumerate(('20260831','20260901')):
                ct=self.write(root/f'ct{i}.dcm','CT',f'1.2.3.8{i}')
                ct.SeriesInstanceUID='1.2.3.10';ct.AcquisitionDate=date
                ct.save_as(root/f'ct{i}.dcm',enforce_file_format=True)
            with self.assertRaises(ValueError):read_fraction_dicoms([root/'ct0.dcm',root/'ct1.dcm'],'QA')
            roi=deepcopy(rd.StructureSetROISequence[0]);roi.ROINumber=2;roi.ROIName='PointA_L'
            rd.StructureSetROISequence.append(roi)
            contour=deepcopy(rd.ROIContourSequence[0]);contour.ReferencedROINumber=2;rd.ROIContourSequence.append(contour)
            dose=deepcopy(rd.RTDoseROISequence[0]);dose.ReferencedROINumber=2;rd.RTDoseROISequence.append(dose)
            rd.save_as(root/'rd.dcm',enforce_file_format=True)
            result=read_fraction_dicoms([root/'rd.dcm'],'QA')
            self.assertEqual([p['target'] for p in result['points']],[None,None])

    def test_dicom_first_and_later_dvh(self):
        from unittest.mock import patch
        from embrace_core import DVH
        from embrace_dicom import read_fraction_dicoms
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);self.fixture(root)
            result=read_fraction_dicoms([root/'rd.dcm',root/'rp.dcm'],'')
            self.assertEqual(result['patient_id'],'QA')
            course=Course();course.patient_id=result['patient_id']
            course.point_doses[0]={'point_a_left':result['points'][0]['dose']}
            course.point_records[0]=result['points'];course.point_source_dates[0]=result['date']
            course.ct_dates[0]='2026-08-31'
            parsed=DVH('QA Patient','QA','Plan',{},[])
            with patch('embrace_core.parse_dvh',return_value=parsed):
                course.load(0,'first.txt')
                self.assertEqual(course.point_doses[0]['point_a_left'],4.924310)
                self.assertEqual(course.ct_dates[0],'2026-08-31')
                course.load(0,'replacement.txt')
                self.assertEqual(course.point_doses[0],{})

    def test_rp_name_and_date_are_from_plan(self):
        from embrace_dicom import read_fraction_dicoms
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);rd,rp=self.fixture(root)
            rp.RTPlanLabel='QA Plan';rp.RTPlanDate='20260830'
            rp.save_as(root/'rp.dcm',enforce_file_format=True)
            result=read_fraction_dicoms([root/'rp.dcm',root/'rd.dcm'],'QA')
            self.assertEqual(result['rp_name'],'QA Plan')
            self.assertEqual(result['rp_date'],'2026-08-30')
            self.assertEqual(result['date'],'2026-08-31')
            self.assertIsNone(read_fraction_dicoms([root/'rd.dcm'],'QA')['rp_name'])
            del rp.RTPlanDate;rp.save_as(root/'rp.dcm',enforce_file_format=True)
            self.assertEqual(read_fraction_dicoms([root/'rp.dcm'],'QA')['rp_date'],'')
            course=Course();course.rp_names[3]='QA Plan';course.rp_dates[3]='2026-08-30'
            course.set_count(3)
            self.assertEqual(course.rp_names[3],'');self.assertEqual(course.rp_dates[3],'')
