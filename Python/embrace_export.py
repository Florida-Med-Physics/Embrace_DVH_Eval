"""Surgical XLSX updates: retain template formatting, namespaces and formulas."""
from pathlib import Path
import os
import re
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape
from embrace_core import METRICS

NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'


def sheet_paths(archive):
    root = ET.fromstring(archive.read('xl/workbook.xml'))
    rels = {r.attrib['Id']: r.attrib['Target'] for r in ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))}
    return {s.attrib['name']: ('xl/'+rels[s.attrib['{'+REL+'}id']] if not rels[s.attrib['{'+REL+'}id']].startswith('/') else rels[s.attrib['{'+REL+'}id']].lstrip('/')) for s in root.find('{'+NS+'}sheets')}


def replace_cell(xml, ref, value):
    pattern = r'<c\b(?=[^>]*\br="'+ref+r'")(?:[^>]*/>|[^>]*>.*?</c>)'
    match = re.search(pattern, xml, flags=re.S)
    if not match:
        raise ValueError(f'Template is missing expected cell {ref}.')
    attributes = re.match(r'<c\b([^>]*?)/?>', match[0])[1]
    attributes = re.sub(r'\s+t="[^"]*"', '', attributes)
    if value is None:
        cell = f'<c{attributes}/>'
    elif isinstance(value, str):
        cell = f'<c{attributes} t="inlineStr"><is><t xml:space="preserve">{escape(value)}</t></is></c>'
    else:
        cell = f'<c{attributes}><v>{value:.15g}</v></c>'
    return xml[:match.start()] + cell + xml[match.end():]


def export_workbook(course, template, output):
    if course.mode=='Cylinder': return export_cylinder_workbook(course,output)
    template, output = Path(template), Path(output)
    if template.resolve() == output.resolve():
        raise ValueError('Choose a different output file; the template must be preserved.')
    if not any(v is not None for values in course.values[:course.count] for v in values.values()):
        raise ValueError('There are no brachytherapy fraction values to export.')
    updates = {'C3': (course.patient + ('    MRN: '+course.patient_id if course.patient_id else '')).strip() or None,
               'C6': course.dose_per_fx, 'C7': course.prior_fractions}
    for key, metric in METRICS.items():
        # H is the template's sixth fraction: always clear it.
        for fx, col in enumerate('CDEFGH'):
            updates[f'{col}{metric.row}'] = course.values[fx].get(key) if fx < course.count else None
    temporary = None
    try:
        with zipfile.ZipFile(template) as src:
            sheets = {n:p for n,p in sheet_paths(src).items() if 'FX1-4' in n.upper()}
            if not sheets:
                raise ValueError('No worksheet containing FX1-4 was found.')
            fd, temporary = tempfile.mkstemp(suffix='.xlsx', dir=output.parent)
            os.close(fd)
            with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as dst:
                for item in src.infolist():
                    data = src.read(item.filename)
                    if item.filename in sheets.values():
                        xml = data.decode('utf-8')
                        for ref, value in updates.items():
                            xml = replace_cell(xml, ref, value)
                        # Remove stale formula caches; Excel performs full recalculation.
                        xml = re.sub(r'(<f\b[^>]*(?:/>|>.*?</f>))\s*<v(?:\s[^>]*)?>.*?</v>', r'\1', xml, flags=re.S)
                        data = xml.encode('utf-8')
                    elif item.filename == 'xl/workbook.xml':
                        xml = data.decode('utf-8')
                        calc = '<calcPr calcMode="auto" fullCalcOnLoad="1" forceFullCalc="1"/>'
                        xml = re.sub(r'<calcPr\b[^>]*/>', calc, xml) if '<calcPr' in xml else xml.replace('</workbook>', calc+'</workbook>')
                        data = xml.encode('utf-8')
                    dst.writestr(item, data)
        os.replace(temporary, output)
        return list(sheets)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def export_cylinder_workbook(course, output):
    """Standalone BT-only worksheet; the EMBRACE template stays untouched."""
    from embrace_core import eqd2
    output=Path(output)
    if not any(course.values[:course.count]): raise ValueError('No fraction values to export.')
    n=course.count
    rows=[['PORTEC-4 EQD2'],['Patient',course.patient,'ID',course.patient_id],
          ['Prescription [Gy / Fx]',course.prescription_gy,'Fractions',n],
          ['Structure / dose parameter']+[f'Fx {i+1}' for i in range(n)]+['Total BT EQD2 [Gy]']]
    input_rows=set();headers={1,4}
    for title,key,metrics in course.structures:
        rows.append([title]);headers.add(len(rows))
        for metric in metrics:
            k=f'{key}_{metric.key}'
            rows.append([metric.label]+[course.values[i].get(k) for i in range(n)])
            if metric.ab:
                input_rows.add(len(rows))
                rows.append([metric.label.replace('[Gy]',f'EQD2{metric.ab} [Gy]')]+[
                    eqd2(course.values[i][k],metric.ab) if course.values[i].get(k) is not None else None
                    for i in range(n)]+[course.total(k)])
    data=[]
    for r,row in enumerate(rows,1):
        cells=[]
        for c,value in enumerate(row):
            ref=f'{chr(65+c)}{r}'
            style=1 if r in headers else (2 if r in input_rows and c>0 else 0)
            if value is None: cells.append(f'<c r="{ref}" s="{style}"/>')
            elif isinstance(value,(int,float)):cells.append(f'<c r="{ref}" s="{style}"><v>{value}</v></c>')
            else:cells.append(f'<c r="{ref}" s="{style}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>')
        data.append(f'<row r="{r}">'+''.join(cells)+'</row>')
    files={
      '[Content_Types].xml':'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>',
      '_rels/.rels':'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
      'xl/workbook.xml':f'<workbook xmlns="{NS}" xmlns:r="{REL}"><sheets><sheet name="PORTEC-4 EQD2" sheetId="1" r:id="rId1"/></sheets></workbook>',
      'xl/_rels/workbook.xml.rels':f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="{REL}/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="{REL}/styles" Target="styles.xml"/></Relationships>',
      'xl/styles.xml':f'<styleSheet xmlns="{NS}"><fonts count="1"><font><sz val="11"/><name val="Arial"/></font></fonts><fills count="4"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FFE6E9ED"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFD9EFF7"/></patternFill></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs><cellXfs count="3"><xf fontId="0" fillId="0" borderId="0" xfId="0"/><xf fontId="0" fillId="2" borderId="0" xfId="0" applyFill="1"/><xf fontId="0" fillId="3" borderId="0" xfId="0" applyFill="1"/></cellXfs></styleSheet>',
      'xl/worksheets/sheet1.xml':f'<worksheet xmlns="{NS}"><cols><col min="1" max="1" width="32" customWidth="1"/><col min="2" max="7" width="22" customWidth="1"/></cols><sheetData>'+''.join(data)+'</sheetData></worksheet>'}
    fd,temp=tempfile.mkstemp(suffix='.xlsx',dir=output.parent);os.close(fd)
    try:
        with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED) as archive:
            for name,xml in files.items():archive.writestr(name,xml)
        os.replace(temp,output)
    finally:
        if os.path.exists(temp):os.unlink(temp)
    return ['PORTEC-4 EQD2']
