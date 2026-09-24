"""Relative DVH plots and source-data tables for explicitly imported fractions."""
import io
import math
from xml.sax.saxutils import escape
from reportlab.graphics.shapes import Drawing, Line, PolyLine, Rect, String
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, Table, TableStyle, PageBreak, Spacer, Image
from embrace_core import STRUCTURES, dose_at_volume

PALETTE={'bladder':'#e9a600','bowel':'#d76564','sigmoid':'#36a45b','ctvhr':'#d325cc','ctvir':'#b8a600','gtvres':'#00aabb','rectum':'#ed8959'}
STYLE=ParagraphStyle('DVH appendix',fontName='Helvetica',fontSize=8,leading=10)

def p(text): return Paragraph(escape(str(text)),STYLE)


def relative_rows(curve,prescription):
    if prescription<=0 or curve['total_cc']<=0:
        raise ValueError('Positive prescription and ROI volume are required for relative DVHs.')
    return [(dose*100 if curve['relative'] else dose/prescription*100, volume/curve['total_cc']*100)
            for dose,volume in curve['rows']]


def metric_rows(parsed,prescription):
    result=[]
    for _,key,metrics in STRUCTURES:
        curve=parsed.curves.get(key)
        if not curve: continue
        total=curve['total_cc']
        for metric in metrics:
            if not metric.ab: continue
            target=total*float(metric.key[1:])/100 if metric.ab==10 else (.1 if metric.key=='D0p1' else 2)
            volumes=[v for _,v in curve['rows']]
            dose=None
            if min(volumes)<=target<=max(volumes):
                value=dose_at_volume(curve['rows'],target)
                dose=value*prescription if curve['relative'] else value
            result.append((curve['name'],metric.label,dose/prescription*100 if dose is not None else None,
                           dose*100 if dose is not None else None,target/total*100,target))
    return result


def plot(parsed,prescription):
    drawing=Drawing(720,244)
    x,y,w,h=48,29,535,195
    all_curves=[(key,curve,relative_rows(curve,prescription)) for key,curve in parsed.curves.items()]
    xmax=max(100,math.ceil(max((d for _,_,rows in all_curves for d,v in rows),default=100)/50)*50)
    drawing.add(Rect(x,y,w,h,fillColor=colors.HexColor('#f3f3f3'),strokeColor=colors.black,strokeWidth=.5))
    for i in range(6):
        yy=y+h*i/5
        drawing.add(Line(x,yy,x+w,yy,strokeColor=colors.HexColor('#c3c3c3'),strokeWidth=.4))
        drawing.add(String(x-8,yy-3,str(i*20),fontSize=7,textAnchor='end'))
    for i in range(9):
        xx=x+w*i/8
        drawing.add(Line(xx,y,xx,y+h,strokeColor=colors.HexColor('#c3c3c3'),strokeWidth=.4))
        drawing.add(String(xx,y-11,f'{xmax*i/8:g}',fontSize=7,textAnchor='middle'))
    drawing.add(String(x,y+h+9,'Volume [%]',fontSize=8))
    drawing.add(String(x+w,y-25,'Dose [% of prescription]',fontSize=8,textAnchor='end'))
    for i,(key,curve,rows) in enumerate(all_curves):
        color=colors.HexColor(PALETTE.get(key,'#555555'))
        points=[coordinate for d,v in rows for coordinate in (x+w*d/xmax,y+h*v/100)]
        if len(points)>=4: drawing.add(PolyLine(points,strokeColor=color,strokeWidth=1.1))
        drawing.add(Line(595,214-i*20,607,214-i*20,strokeColor=color,strokeWidth=2))
        # Structure keys keep the chart legend compact; full source ROI names are in the table.
        drawing.add(String(612,211-i*20,key.upper(),fontSize=7,fillColor=colors.black))
    return drawing


def appendix(course):
    story=[]
    for fx in range(course.count):
        parsed=course.dvhs[fx]
        modality=course.modalities[fx] or 'Not specified'
        context=f'Patient: {course.patient or "Not specified"} | ID: {course.patient_id or "Not specified"} | Fx {fx+1} | Imaging: {modality}'
        screenshot=course.screenshots[fx]
        if screenshot:
            story += [PageBreak(),p(f'ONCENTRA / ISODOSE - FRACTION {fx+1}'),p(context),Spacer(1,12)]
            image=Image(io.BytesIO(screenshot))
            scale=min(720/image.imageWidth,465/image.imageHeight)
            image.drawWidth=image.imageWidth*scale; image.drawHeight=image.imageHeight*scale
            story.append(image)
        if parsed and parsed.curves:
            story += [PageBreak(),p(f'RELATIVE DVH - FRACTION {fx+1}'),p(context),
                      p(f'Source: {course.files[fx]} | Prescription: {course.prescription_gy:g} Gy = 100%'),
                      plot(parsed,course.prescription_gy)]
            data=[['ROI','Metric','Dose [%]','Dose [cGy]','Volume [%]','Volume [cc]']]
            for name,metric,*values in metric_rows(parsed,course.prescription_gy):
                data.append([p(name),metric]+['' if value is None else f'{value:.2f}' for value in values])
            table=Table(data,colWidths=[215,115,95,100,100,95],repeatRows=1)
            commands=[('FONTNAME',(0,0),(-1,-1),'Helvetica'),('FONTSIZE',(0,0),(-1,-1),7.5),
                      ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e6e9ed')),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
                      ('ALIGN',(2,0),(-1,-1),'RIGHT'),('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                      ('TOPPADDING',(0,0),(-1,-1),1),('BOTTOMPADDING',(0,0),(-1,-1),1),
                      ('LINEBELOW',(0,0),(-1,0),.5,colors.gray)]
            previous=None
            for row,item in enumerate(data[1:],1):
                name=item[0].text
                if name!=previous: commands.append(('LINEABOVE',(0,row),(-1,row),.3,colors.gray))
                commands.append(('FONTNAME',(4 if 'D0.' not in item[1] and 'D2cc' not in item[1] else 5,row),(4 if 'D0.' not in item[1] and 'D2cc' not in item[1] else 5,row),'Helvetica-Bold'))
                previous=name
            table.setStyle(TableStyle(commands))
            story += [table,Spacer(1,5),p('Curve and table use the imported DVH, not manually edited worksheet doses. Blank doses are outside the sampled DVH range.')]
    return story
