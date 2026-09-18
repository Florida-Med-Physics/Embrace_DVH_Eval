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
STATUS = {'neutral': colors.white, 'pass': colors.HexColor('#d5ead8'),
          'warn': colors.HexColor('#fff0bb'), 'fail': colors.HexColor('#f6d0cd')}


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


def export_pdf(course, output):
    """Export the current course without changing its values or requiring Excel."""
    output = Path(output)
    if not any(v is not None for values in course.values[:course.count] for v in values.values()):
        raise ValueError('There are no brachytherapy fraction values to export.')
    normal = ParagraphStyle('Body', fontName='Helvetica', fontSize=9, leading=12, textColor=INK)
    small = ParagraphStyle('Small', parent=normal, fontSize=8, leading=10)
    title = ParagraphStyle('Title', parent=normal, fontName='Helvetica-Bold', fontSize=16, leading=20, textColor=UF_BLUE)
    section_style = ParagraphStyle('Section', parent=normal, fontName='Helvetica-Bold', fontSize=11, leading=14)
    cell_style = ParagraphStyle('Cell', parent=small, fontSize=7.5, leading=9, alignment=1, textColor=colors.white)
    def p(value, style=normal):
        return Paragraph(escape(str(value)), style)

    story = []
    for page, (heading, definitions) in enumerate((('TARGETS', STRUCTURES[:3]), ('ORGANS AT RISK', STRUCTURES[3:]))):
        if page:
            story.append(PageBreak())
        story += [p('EMBRACE-2 | EQD2 report', title), Spacer(1,5),
                  p(f'Patient: {course.patient or "Not specified"}    |    Patient ID: {course.patient_id or "Not specified"}'),
                  p(f'Brachytherapy: {course.count} fractions'),
                  p(f'Prior RT: {fmt(course.dose_per_fx)} Gy x {course.prior_fractions} fractions = {fmt(course.dose_per_fx*course.prior_fractions)} Gy'),
                  p(f'Prior RT EQD2: {fmt(course.baseline(10))} Gy (a/b = 10)    |    {fmt(course.baseline(3))} Gy (a/b = 3)'),
                  Spacer(1,10), p(heading,section_style), Spacer(1,5)]
        goals = ('Planning goal','Tolerance') if page == 0 else ('Soft constraint','Hard constraint')
        headers = ['Structure / metric']+[f'Fx {i+1}' for i in range(course.count)]+['BT + EBRT\nEQD2 [Gy]',*goals]
        rows = [[p(h.replace('\n',' '),cell_style) for h in headers]]
        widths = [148]+[38]*course.count+[72,65,65]
        # Use the full printable width, allocating extra room to the metric label.
        widths[0] += 528-sum(widths)
        commands = [('FONTNAME',(0,0),(-1,-1),'Helvetica'), ('FONTSIZE',(0,0),(-1,-1),8),
                    ('TEXTCOLOR',(0,0),(-1,-1),INK), ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                    ('ALIGN',(1,0),(-1,-1),'CENTER'), ('BACKGROUND',(0,0),(-1,0),UF_BLUE),
                    ('TOPPADDING',(0,0),(-1,-1),3), ('BOTTOMPADDING',(0,0),(-1,-1),3),
                    ('LINEBELOW',(0,0),(-1,0),.6,colors.HexColor('#b8c0c7'))]
        for name,key,metrics in definitions:
            r=len(rows)
            rows.append([name]+['']*(course.count+3))
            commands += [('SPAN',(0,r),(-1,r)),('BACKGROUND',(0,r),(-1,r),GRAY),
                         ('FONTNAME',(0,r),(-1,r),'Helvetica-Bold'),('TEXTCOLOR',(0,r),(-1,r),UF_BLUE), ('NOSPLIT',(0,r),(-1,r+1))]
            for metric in metrics:
                k=f'{key}_{metric.key}'
                rows.append([metric.label]+[fmt(course.values[fx].get(k)) for fx in range(course.count)]+['','',''])
                if metric.ab:
                    rows.append([metric.label.replace('[Gy]',f'EQD2 (a/b {metric.ab}) [Gy]')]+
                                [fmt(eqd2(course.values[fx][k],metric.ab)) if course.values[fx].get(k) is not None else '' for fx in range(course.count)]+
                                [fmt(course.total(k)),metric.goal,metric.hard])
                    r=len(rows)-1
                    commands += [('BACKGROUND',(course.count+1,r),(course.count+1,r),STATUS[status(course.total(k),metric)]),
                                 ('FONTNAME',(course.count+1,r),(course.count+1,r),'Helvetica-Bold'),
                                 ('LINEBELOW',(0,r),(-1,r),.2,colors.HexColor('#e3e6e9'))]
        table=Table(rows,colWidths=widths,repeatRows=1,hAlign='LEFT')
        table.setStyle(TableStyle(commands))
        story += [table,Spacer(1,7),p('Green: goal met | Yellow: tolerance met | Red: tolerance exceeded or not met',small),
                  p('Blank metrics are not included in totals. Values display one decimal; calculations retain stored precision.',small)]
        if page == 1:
            story += [Spacer(1,9),p('FRACTION SOURCES',section_style)]
            for fx in range(course.count):
                story.append(p(f'Fx {fx+1} | Plan: {course.plans[fx] or "Not specified"} | {course.files[fx] or "Manual / not loaded"}',small))
    timestamp=datetime.now().strftime('%Y-%m-%d %H:%M')
    def footer(canvas, doc):
        draw_letterhead(canvas)
        canvas.setFont('Helvetica',8)
        canvas.setFillColor(INK)
        canvas.drawString(42,22,f'UFHPTI | EQD2 | Exported {timestamp}')
        canvas.drawRightString(570,22,f'Page {doc.page}')
    fd,temp=tempfile.mkstemp(suffix='.pdf',dir=output.parent)
    os.close(fd)
    try:
        doc=SimpleDocTemplate(temp,pagesize=letter,leftMargin=36,rightMargin=36,topMargin=68,bottomMargin=36,
                              title='EMBRACE-2 EQD2 report',author='EMBRACE EQD2')
        doc.build(story,onFirstPage=footer,onLaterPages=footer)
        os.replace(temp,output)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


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
    for page,(heading,definitions) in enumerate((('TARGETS',STRUCTURES[:3]),('ORGANS AT RISK',STRUCTURES[3:]))):
        if page:
            story.append(PageBreak())
        story += [p('EMBRACE-2 | Plan comparison',title),Spacer(1,5),
                  p(f'Patient: {first.patient or "Not specified"}    |    Patient ID: {first.patient_id or "Not specified"}'),
                  p(f'Each plan repeated for {course.count} fractions. Prior RT: {fmt(course.dose_per_fx)} Gy x {course.prior_fractions}.'),
                  p(f'Prior RT EQD2: {fmt(course.baseline(10))} Gy (a/b 10) | {fmt(course.baseline(3))} Gy (a/b 3).'),Spacer(1,7)]
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
                rows.append([metric.label]+[fmt(plan.metrics.get(k)) if plan else '' for plan in comparison.plans]+['',''])
                if metric.ab:
                    totals=[scenario.total(k) if scenario else None for scenario in scenarios]
                    rows.append([metric.label.replace('[Gy]','total EQD2 [Gy]')]+[fmt(total) for total in totals]+[metric.goal,metric.hard])
                    r=len(rows)-1
                    for slot,total in enumerate(totals):
                        commands += [('BACKGROUND',(slot+1,r),(slot+1,r),STATUS[status(total,metric)]),('FONTNAME',(slot+1,r),(slot+1,r),'Helvetica-Bold')]
                    commands.append(('LINEBELOW',(0,r),(-1,r),.2,colors.HexColor('#e3e6e9')))
        table=Table(rows,colWidths=[144,62,62,62,62,62,74],repeatRows=1,hAlign='LEFT')
        table.setStyle(TableStyle(commands))
        story += [table,Spacer(1,7),p('Physical dose rows: one fraction. Total EQD2 rows: all fractions + prior RT.',small),
                  p('Green: goal met | Yellow: tolerance met | Red: tolerance exceeded or not met',small),
                  p('Blank metrics are not included. Values display one decimal; calculations retain stored precision.',small)]
    timestamp=datetime.now().strftime('%Y-%m-%d %H:%M')
    def footer(canvas,doc):
        draw_letterhead(canvas)
        canvas.setFont('Helvetica',8)
        canvas.drawString(42,22,f'UFHPTI | Plan comparison | Exported {timestamp}')
        canvas.drawRightString(570,22,f'Page {doc.page}')
    fd,temp=tempfile.mkstemp(suffix='.pdf',dir=output.parent)
    os.close(fd)
    try:
        doc=SimpleDocTemplate(temp,pagesize=letter,leftMargin=36,rightMargin=36,topMargin=68,bottomMargin=36,title='EMBRACE-2 Plan Comparison',author='EMBRACE EQD2')
        doc.build(story,onFirstPage=footer,onLaterPages=footer)
        os.replace(temp,output)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
