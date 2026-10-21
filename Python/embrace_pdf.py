"""Printable dashboard reports with one-decimal values and repeated headers."""
from datetime import datetime
from pathlib import Path
import os
import tempfile
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, PageBreak, KeepTogether

from embrace_core import STRUCTURES, eqd2, fmt, status

# Colors carried over from the supplied MATLAB application's UF palette.
UF_BLUE = colors.HexColor('#002169')
UF_ORANGE = colors.HexColor('#fa4a00')
INK = colors.HexColor('#17212b')
GRAY = colors.HexColor('#e9ecef')
STATUS = {'neutral': colors.white, 'pass': colors.HexColor('#73bf6e'),
          'warn': colors.HexColor('#f5cc52'), 'fail': colors.HexColor('#e0574d')}


def draw_trial_reference(canvas, width):
    canvas.saveState()
    canvas.setFillColor(INK)
    canvas.setFont('Helvetica',6)
    canvas.drawString(36,39,'Reference: Pötter R, Tanderup K, Kirisits C, et al. The EMBRACE II study: The outcome and prospect of two decades')
    canvas.drawString(36,31,'of evolution within the GEC-ESTRO GYN working group and the EMBRACE studies. Clin Transl Radiat Oncol. 2018;9:48-60.')
    canvas.drawString(36,23,'doi:10.1016/j.ctro.2018.01.001')
    canvas.linkURL('https://doi.org/10.1016/j.ctro.2018.01.001',(36,21,210,30),relative=0)
    canvas.restoreState()


def draw_letterhead(canvas):
    """Text-based UFHPTI treatment pending a supplied institutional template."""
    canvas.saveState()
    canvas.setFillColor(UF_BLUE)
    canvas.setFont('Helvetica-Bold',22)
    canvas.drawString(42,754,'UFHPTI')
    canvas.setFont('Helvetica',9)
    canvas.drawRightString(570,758,'EMBRACE-II / EQD2')
    canvas.setStrokeColor(UF_BLUE)
    canvas.setLineWidth(1)
    canvas.line(42,741,570,741)
    canvas.setStrokeColor(UF_ORANGE)
    canvas.setLineWidth(3)
    canvas.line(42,741,108,741)
    canvas.restoreState()


def export_pdf(course, output, fraction=0, worksheet_only=False):
    """Print the dashboard data in the EMBRACE worksheet's column order."""
    output=Path(output)
    if not any(v is not None for values in course.values[:course.count] for v in values.values()):
        raise ValueError('There are no brachytherapy fraction values to export.')
    normal=ParagraphStyle('Worksheet',fontName='Helvetica',fontSize=8,leading=10,textColor=INK)
    head=ParagraphStyle('WorksheetHeader',parent=normal,fontName='Helvetica-Bold',alignment=1)
    small=ParagraphStyle('WorksheetSmall',parent=normal,fontSize=7,leading=9)
    title=ParagraphStyle('WorksheetTitle',parent=normal,fontName='Helvetica-Bold',fontSize=13,leading=16)
    blue=colors.HexColor('#d9eff7')
    band=colors.HexColor('#e6e9ed')
    def p(value,style=normal):
        return Paragraph(escape(str(value)).replace('\n','<br/>'),style)
    def style_table(table,extra=()):
        table.setStyle(TableStyle([
            ('FONTNAME',(0,0),(-1,-1),'Helvetica'),('FONTSIZE',(0,0),(-1,-1),8),
            ('VALIGN',(0,0),(-1,-1),'MIDDLE'),('ALIGN',(1,0),(-1,-1),'CENTER'),
            ('TOPPADDING',(0,0),(-1,-1),.5),('BOTTOMPADDING',(0,0),(-1,-1),.5),
            ('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),
            ('GRID',(0,0),(-1,-1),.3,colors.HexColor('#b8c0c7')),
            ('BACKGROUND',(0,0),(-1,0),band),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
        ]+list(extra)))
        return table
    story=[]
    for page,(heading,definitions) in enumerate(course.sections):
        if page: story.append(PageBreak())
        story += [p(course.title+' | PHYSICAL - BIOLOGICAL DOCUMENTATION OF HDR BT',title),Spacer(1,5),
                  p(f'PATIENT: {course.patient or "Not specified"}    |    ID: {course.patient_id or "Not specified"}'),
                  p(f'BRACHYTHERAPY: {fmt(course.prescription_gy)} Gy x {course.count} fractions    |    Prescription BT EQD2 (a/b 10): {fmt(course.prescription_eqd2())} Gy'),Spacer(1,7)]
        prior=[['EXTERNAL BEAM THERAPY','Value','TUMOUR EQD2 [Gy]\n(a/b = 10)','OAR EQD2 [Gy]\n(a/b = 3)'],
               ['Dose per fraction [Gy]',fmt(course.dose_per_fx),'',''],
               ['Fractions without central shield',str(course.prior_fractions),fmt(course.baseline(10)),fmt(course.baseline(3))],
               ['Total dose [Gy]',fmt(course.dose_per_fx*course.prior_fractions),fmt(course.baseline(10)),fmt(course.baseline(3))]]
        prior[0]=[p(v,head) for v in prior[0]]
        if course.mode=='Cylinder':
            pass
        elif page==0:
            story += [style_table(Table(prior,colWidths=[300,100,160,160]),[('BACKGROUND',(1,1),(1,2),blue)]),Spacer(1,8)]
        else:
            story += [p(f'EXTERNAL BEAM THERAPY: {fmt(course.dose_per_fx)} Gy x {course.prior_fractions} | EQD2 tumour: {fmt(course.baseline(10))} Gy | EQD2 OAR: {fmt(course.baseline(3))} Gy'),Spacer(1,8)]
        goals=('Planning goal','Tolerance') if page==0 else ('Soft constraint','Hard constraint')
        n=course.count
        widths=[720-(48*n+65+75+70+70)]+[48]*n+[65,75,70,70]
        labels=['Structure / dose parameter']+[f'F {i+1}' for i in range(n)]+['TOTAL BT\nEQD2 [Gy]','BT + EBRT\nEQD2 [Gy]',*goals]
        rows=[[p(v,head) for v in labels]]
        commands=[]
        # Fractions retain their source plan names within the worksheet header.
        rows.append(['Localization (MR / CT)']+[p(course.modalities[i] or 'Not set',small) for i in range(n)]+['']*4)
        rows.append(['Plan / source']+[p(course.files[i] or course.plans[i] or 'Manual',small) for i in range(n)]+['']*4)
        rows.append(['Date']+[p(course.dvhs[i].source_date or 'Unavailable',small) if course.dvhs[i] else p('Not imported',small) for i in range(n)]+['']*4)
        for name,key,metrics in definitions:
            r=len(rows)
            rows.append([name]+['']*(n+4))
            commands += [('SPAN',(0,r),(-1,r)),('BACKGROUND',(0,r),(-1,r),band),
                         ('FONTNAME',(0,r),(-1,r),'Helvetica-Bold'),('LINEABOVE',(0,r),(-1,r),1,INK),
                         ('TOPPADDING',(0,r),(-1,r),4),('NOSPLIT',(0,r),(-1,r+1))]
            for metric in metrics:
                k=f'{key}_{metric.key}'
                r=len(rows)
                rows.append([metric.label]+[fmt(course.values[i].get(k)) for i in range(n)]+['']*4)
                if metric.ab:
                    commands += [('BACKGROUND',(1,r),(n,r),blue),('NOSPLIT',(0,r),(-1,r+1))]
                    values=[eqd2(course.values[i][k],metric.ab) if course.values[i].get(k) is not None else None for i in range(n)]
                    bt=sum(v for v in values if v is not None) if any(v is not None for v in values) else None
                    rows.append([metric.label.replace('[Gy]',f'EQD2{metric.ab} [Gy]')]+[fmt(v) for v in values]+[fmt(bt),fmt(course.total(k)),metric.goal,metric.hard])
                    r=len(rows)-1
                    commands += [('BACKGROUND',(n+2,r),(n+2,r),STATUS[status(course.total(k),metric)]),('FONTNAME',(n+1,r),(n+2,r),'Helvetica-Bold')]
        if course.mode=='Cylinder':
            rows=[row[:n+2] for row in rows]
            widths=[720-65*n-100]+[65]*n+[100]
            commands=[command for command in commands
                      if not (isinstance(command[1],tuple) and
                              (command[1][0]>n+1 or command[2][0]>n+1))]
        section=Table([[heading]],colWidths=[720])
        section.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),INK),('TEXTCOLOR',(0,0),(-1,-1),colors.white),('FONTNAME',(0,0),(-1,-1),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),10),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4)]))
        story += [section,style_table(Table(rows,colWidths=widths,repeatRows=4,hAlign='LEFT'),commands)]
    from embrace_dvh_report import appendix
    front=[] if worksheet_only else appendix(course,fraction)
    if front:
        if isinstance(front[0],PageBreak): front.pop(0)
        story=front+[PageBreak()]+story
    timestamp=datetime.now().strftime('%Y-%m-%d %H:%M')
    def footer(canvas,doc):
        canvas.setFont('Helvetica',7)
        canvas.setFillColor(INK)
        if course.mode=='GYN': draw_trial_reference(canvas,792)
        canvas.drawString(36,10,f'UFHPTI | {course.title if course.mode=="Cylinder" else "EMBRACE EQD2"} | {timestamp}')
        canvas.drawRightString(756,10,f'Page {doc.page}')
    fd,temp=tempfile.mkstemp(suffix='.pdf',dir=output.parent)
    os.close(fd)
    try:
        doc=SimpleDocTemplate(temp,pagesize=(792,612),leftMargin=30,rightMargin=30,topMargin=18,bottomMargin=48,title=course.title+' worksheet',author='EMBRACE EQD2')
        doc.build(story,onFirstPage=footer,onLaterPages=footer)
        os.replace(temp,output)
    finally:
        if os.path.exists(temp): os.unlink(temp)


def export_comparison_pdf(comparison, course, output):
    """Export up to four repeated-plan scenarios using the same course model."""
    if not any(comparison.plans):
        raise ValueError('Load at least one comparison plan before exporting.')
    output=Path(output)
    normal=ParagraphStyle('CompareBody',fontName='Helvetica',fontSize=9,leading=12,textColor=INK)
    small=ParagraphStyle('CompareSmall',parent=normal,fontSize=8,leading=10)
    title=ParagraphStyle('CompareTitle',parent=normal,fontName='Helvetica-Bold',fontSize=16,leading=20,textColor=UF_BLUE)
    head=ParagraphStyle('CompareHeader',parent=small,alignment=1,textColor=colors.white)
    def p(text,style=normal):
        return Paragraph(escape(str(text)),style)
    scenarios=[comparison.scenario(i,course) for i in range(4)]
    first=next(plan for plan in comparison.plans if plan)
    story=[]
    for page,(heading,definitions) in enumerate(course.sections):
        if page:
            story.append(PageBreak())
        story += [p(course.title+' | Plan comparison',title),Spacer(1,5),
                  p(f'Patient: {first.patient or "Not specified"}    |    Patient ID: {first.patient_id or "Not specified"}'),
                  p(f'Prescription: {fmt(course.prescription_gy)} Gy x {course.count} fractions. Prior RT: {fmt(course.dose_per_fx)} Gy x {course.prior_fractions}.'),
                  p(f'Prior RT EQD2: {fmt(course.baseline(10))} Gy (a/b 10) | {fmt(course.baseline(3))} Gy (a/b 3).'),Spacer(1,7)]
        if course.mode=='Cylinder':
            story=story[:-3]+[p(f'Prescription: {fmt(course.prescription_gy)} Gy x {course.count} fractions. Total BT EQD2.'),Spacer(1,7)]
        if page==0:
            for i,plan in enumerate(comparison.plans):
                if plan:
                    story.append(p(f'Plan {i+1}: {plan.plan or "Unnamed plan"} | {comparison.files[i]}',small))
            story.append(Spacer(1,7))
        story.append(p(heading))
        story.append(Spacer(1,5))
        rows=[[p(t,head) for t in ['Structure / metric','Plan 1','Plan 2','Plan 3','Plan 4','Goal / soft','Tolerance / hard']]]
        commands=[('FONTNAME',(0,0),(-1,-1),'Helvetica'),('FONTSIZE',(0,0),(-1,-1),8),
                  ('VALIGN',(0,0),(-1,-1),'MIDDLE'),('ALIGN',(1,0),(-1,-1),'CENTER'),
                  ('TEXTCOLOR',(0,0),(-1,-1),INK),('BACKGROUND',(0,0),(-1,0),UF_BLUE),
                  ('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3)]
        for name,key,metrics in definitions:
            r=len(rows)
            rows.append([name]+['']*6)
            commands += [('SPAN',(0,r),(-1,r)),('BACKGROUND',(0,r),(-1,r),GRAY),('FONTNAME',(0,r),(-1,r),'Helvetica-Bold'),('TEXTCOLOR',(0,r),(-1,r),UF_BLUE),('NOSPLIT',(0,r),(-1,r+1))]
            for metric in metrics:
                k=f'{key}_{metric.key}'
                rows.append([metric.label]+[fmt(scenario.values[0].get(k)) if scenario else '' for scenario in scenarios]+['',''])
                if metric.ab:
                    totals=[scenario.total(k) if scenario else None for scenario in scenarios]
                    rows.append([metric.label.replace('[Gy]','total EQD2 [Gy]')]+[fmt(total) for total in totals]+[metric.goal,metric.hard])
                    r=len(rows)-1
                    for slot,total in enumerate(totals):
                        commands += [('BACKGROUND',(slot+1,r),(slot+1,r),STATUS[status(total,metric)]),('FONTNAME',(slot+1,r),(slot+1,r),'Helvetica-Bold')]
                    commands.append(('LINEBELOW',(0,r),(-1,r),.2,colors.HexColor('#e3e6e9')))
        widths=[144,62,62,62,62,62,74]
        if course.mode=='Cylinder':
            # No PORTEC-4 constraints are defined; drop the empty goal columns.
            rows=[row[:5] for row in rows]
            widths=[144,96,96,96,96]
        table=Table(rows,colWidths=widths,repeatRows=1,hAlign='LEFT')
        table.setStyle(TableStyle(commands+[('GRID',(0,0),(-1,-1),.25,colors.black)]))
        story += [table,Spacer(1,7),p('Physical dose rows: one fraction. Total EQD2 rows: all BT fractions.' if course.mode=='Cylinder' else 'Physical dose rows: one fraction. Total EQD2 rows: all fractions + prior RT.',small),
                  p('Blank metrics are not included. Absolute doses stay unchanged; % doses use prescription. Values display one decimal.',small)]
    timestamp=datetime.now().strftime('%Y-%m-%d %H:%M')
    def footer(canvas,doc):
        if course.mode=='GYN': draw_letterhead(canvas)
        canvas.setFont('Helvetica',8)
        if course.mode=='GYN': draw_trial_reference(canvas,612)
        canvas.drawString(42,10,f'UFHPTI | Plan comparison | Exported {timestamp}')
        canvas.drawRightString(570,10,f'Page {doc.page}')
    fd,temp=tempfile.mkstemp(suffix='.pdf',dir=output.parent)
    os.close(fd)
    try:
        doc=SimpleDocTemplate(temp,pagesize=letter,leftMargin=36,rightMargin=36,topMargin=68,bottomMargin=48,title=course.title+' Plan Comparison',author='EMBRACE EQD2')
        doc.build(story,onFirstPage=footer,onLaterPages=footer)
        os.replace(temp,output)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
