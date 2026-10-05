"""Relative DVH plots and source-data tables for explicitly imported fractions."""
import io
import math
from xml.sax.saxutils import escape
from reportlab.graphics.shapes import Drawing, Line, PolyLine, Rect, String
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, Table, TableStyle, PageBreak, Spacer, Image
from embrace_core import STRUCTURES, dose_at_volume

PALETTE={'bladder':'#40bfb5','bowel':'#e08080','sigmoid':'#36a45b','ctvhr':'#348dcb','ctvir':'#dedb00','gtvres':'#cf4545','rectum':'#ed8959'}
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
    drawing=Drawing(720,270)
    x,y,w,h=40,28,555,220
    all_curves=[(key,curve,relative_rows(curve,prescription)) for key,curve in parsed.curves.items()]
    # Match the Oncentra viewing range; retain the original curve and table data.
    xmax=400
    drawing.add(Rect(x,y,w,h,fillColor=colors.HexColor('#eeeeee'),strokeColor=colors.black,strokeWidth=.7))
    for v in range(0,101,10):
        yy=y+h*v/100
        drawing.add(Line(x,yy,x+w,yy,strokeColor=colors.gray,strokeWidth=.35,strokeDashArray=[2,3]))
        drawing.add(String(x-5,yy-2,f'{v:.0f}',fontSize=6,textAnchor='end'))
    for d in range(0,401,50):
        xx=x+w*d/xmax
        drawing.add(Line(xx,y,xx,y+h,strokeColor=colors.gray,strokeWidth=.35,strokeDashArray=[2,3]))
        drawing.add(String(xx,y-10,str(d),fontSize=6,textAnchor='middle'))
    drawing.add(String(x,y+h+9,'Volume [%]',fontSize=7))
    drawing.add(String(x+w,y-23,f'Dose [%]   100% = {prescription:g} Gy',fontSize=7,textAnchor='end'))
    for v in (98,90,50):
        yy=y+h*v/100
        drawing.add(Line(x,yy,x+w,yy,strokeColor=colors.HexColor('#888888'),strokeWidth=.35,strokeDashArray=[1,3]))
        drawing.add(String(x+w-3,yy-7,f'D{v}%',fontSize=6,textAnchor='end'))
    for i,(key,curve,rows) in enumerate(all_curves):
        color=colors.HexColor(PALETTE.get(key,'#555555'))
        visible=[]
        for j,(d,v) in enumerate(rows):
            if d<=xmax: visible.append((d,v))
            elif j and rows[j-1][0]<xmax:
                d0,v0=rows[j-1];visible.append((xmax,v0+(v-v0)*(xmax-d0)/(d-d0)));break
            else: break
        points=[coordinate for d,v in visible for coordinate in (x+w*d/xmax,y+h*v/100)]
        if len(points)>=4: drawing.add(PolyLine(points,strokeColor=color,strokeWidth=.65))
        drawing.add(Rect(606,240-i*14,6,6,fillColor=color,strokeColor=None))
        name=curve['name']
        drawing.add(String(615,240-i*14,name,fontSize=min(7,95/max(len(name)*.55,1))))
    # Label target intersections using the same interpolated values as the table.
    occupied=[]
    for name,metric,dose,_,volume,_ in metric_rows(parsed,prescription):
        if metric not in ('D98 [Gy]','D90 [Gy]','D50 [Gy]') or dose is None or dose>xmax: continue
        xx=x+w*dose/xmax; yy=y+h*volume/100
        label=f'{dose:.2f}';bw=len(label)*3.5+4
        bx=min(xx+3,x+w-bw);by=min(yy+3,y+h-10)
        while any(abs(by-oy)<11 and bx<ox+ow+2 and bx+bw>ox-2 for ox,oy,ow in occupied): by-=12
        occupied.append((bx,by,bw))
        drawing.add(Line(xx,yy,bx,by+4,strokeColor=colors.gray,strokeWidth=.4))
        drawing.add(Rect(bx,by,bw,9,fillColor=colors.white,strokeColor=colors.gray,strokeWidth=.4))
        drawing.add(String(bx+2,by+2,label,fontSize=6))
    return drawing


def appendix(course, fraction=0):
    if not 0 <= fraction < course.count:
        raise ValueError('Choose an active report fraction.')
    story=[]
    for fx in (fraction,):
        parsed=course.dvhs[fx]
        modality=course.modalities[fx] or 'Not specified'
        context=f'Patient: {course.patient or "Not specified"} | ID: {course.patient_id or "Not specified"} | Fx {fx+1} | Localization (MR / CT): {modality}'
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
            data=[['ROI','Dose [%]','Dose [cGy]','Volume [%]','Volume [ccm]']]
            report_rows=sorted(metric_rows(parsed,course.prescription_gy),key=lambda r:(r[0].casefold(),r[4]))
            for name,metric,*values in report_rows:
                data.append([p(name)]+['' if value is None else f'{value:.2f}' for value in values])
            table=Table(data,colWidths=[280,110,110,110,110],repeatRows=1)
            commands=[('FONTNAME',(0,0),(-1,-1),'Helvetica'),('FONTSIZE',(0,0),(-1,-1),7.5),
                      ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e6e9ed')),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
                      ('ALIGN',(1,0),(-1,-1),'RIGHT'),('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                      ('TOPPADDING',(0,0),(-1,-1),1),('BOTTOMPADDING',(0,0),(-1,-1),1),
                      ('LINEBELOW',(0,0),(-1,0),.5,colors.gray)]
            previous=None
            for row,item in enumerate(data[1:],1):
                name=item[0].text
                if name!=previous: commands.append(('LINEABOVE',(0,row),(-1,row),.3,colors.gray))
                metric=report_rows[row-1][1]
                bold_col=4 if metric in ('D0.1cc [Gy]','D2cc [Gy]') else 3
                commands.append(('FONTNAME',(bold_col,row),(bold_col,row),'Helvetica-Bold'))
                previous=name
            table.setStyle(TableStyle(commands))
            story += [table,Spacer(1,5),p('Cumulative DVH: volume receiving at least the plotted dose. Display range: 0-400% of prescription. Table uses the full imported curve; blank doses are outside its sampled range.')]
    return story
