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
