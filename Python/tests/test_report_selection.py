import io
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image
from embrace_attachments import crop_image
from embrace_core import Course,DVH
from embrace_dvh_report import appendix

class ReportSelectionTests(unittest.TestCase):
    def test_crop_uses_original_resolution(self):
        image=Image.new('RGB',(1000,800),'red')
        image.paste('blue',(500,0,1000,800))
        data=io.BytesIO();image.save(data,format='PNG')
        cropped=crop_image(data.getvalue(),(250,0,500,400),(500,400))
        result=Image.open(io.BytesIO(cropped))
        self.assertEqual(result.format,'JPEG')
        self.assertEqual(result.size,(500,800))
        self.assertGreater(result.getpixel((250,400))[2],240)
        with self.assertRaises(ValueError):crop_image(data.getvalue(),(0,0,0,0),(500,400))
    def test_only_selected_fraction_in_front_matter(self):
        c=Course()
        for i in (0,1):
            c.dvhs[i]=DVH('QA','QA',str(i),{},[],curves={'ctvhr':{'name':f'CTV_HR_fx{i+1}','rows':[(0,10),(7,9),(14,0)],'total_cc':10,'relative':False}})
        data=io.BytesIO();Image.new('RGB',(100,100)).save(data,format='PNG')
        c.screenshots[1]=data.getvalue()
        text=' '.join(getattr(item,'text','') for item in appendix(c,1))
        self.assertIn('ONCENTRA / ISODOSE - FRACTION 2',text)
        self.assertIn('RELATIVE DVH - FRACTION 2',text)
        self.assertNotIn('FRACTION 1',text)
        self.assertLess(text.index('ONCENTRA'),text.index('RELATIVE DVH'))
        with self.assertRaises(ValueError):appendix(c,5)
