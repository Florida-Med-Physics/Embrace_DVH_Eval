"""Read exported physical point doses; never use RP prescription as measured dose."""
from datetime import datetime
from pathlib import Path
import math
from embrace_points import suggest_point


def _read(path, patient_id, modality):
    import pydicom
    ds=pydicom.dcmread(path,stop_before_pixels=True)
    if str(getattr(ds,'Modality',''))!=modality:
        raise ValueError(f'Select a {modality} DICOM file.')
    source_id=str(getattr(ds,'PatientID','')).strip()
    if not patient_id or not source_id or source_id.casefold()!=patient_id.strip().casefold():
        raise ValueError('Load the matching patient TXT before selecting the DICOM file.')
    return ds


def _date(ds):
    raw=str(getattr(ds,'ContentDate',''))
    if not raw:raise ValueError('The RD file has no ContentDate; no source date was inferred.')
    return datetime.strptime(raw,'%Y%m%d').date().isoformat()


def point_source_date(path, patient_id=''):
    ds=_read(path,patient_id,'RTDOSE')
    if not getattr(ds,'RTDoseROISequence',None):raise ValueError('Select the RD file containing point doses.')
    return _date(ds)


def _private(ds, group, creator, offset, default=None):
    """Resolve private creator blocks rather than assuming a fixed block slot."""
    try:
        block=ds.private_block(group,creator,create=False)
        return block[offset].value if offset in block else default
    except KeyError:return default


def read_point_doses(rd_path, patient_id, rp_path=None):
    rd=_read(rd_path,patient_id,'RTDOSE')
    if str(getattr(rd,'DoseType',''))!='PHYSICAL':raise ValueError('RD must contain physical doses.')
    seq=getattr(rd,'RTDoseROISequence',None)
    if not seq:raise ValueError('This RD has no exported point doses.')
    names={int(x.ROINumber):str(x.ROIName) for x in getattr(rd,'StructureSetROISequence',[])}
    contours={int(x.ReferencedROINumber):x for x in getattr(rd,'ROIContourSequence',[])}
    groups={}
    if rp_path:
        rp=_read(rp_path,patient_id,'RTPLAN')
        refs=[str(x.ReferencedSOPInstanceUID) for x in getattr(rd,'ReferencedRTPlanSequence',[])]
        if str(rp.SOPInstanceUID) not in refs:raise ValueError('The RD does not reference this RP plan.')
        if getattr(rd,'FrameOfReferenceUID',None)!=getattr(rp,'FrameOfReferenceUID',None):
            raise ValueError('The RD and RP frames do not match.')
        # Oncentra embeds its point-set Structure Set in a private RP sequence.
        for ss in _private(rp,0x300f,'NUCLETRON',0,[]):
            set_names={int(x.ROINumber):str(x.ROIName) for x in getattr(ss,'StructureSetROISequence',[])}
            for roi in getattr(ss,'ROIContourSequence',[]):
                for c in getattr(roi,'ContourSequence',[]):
                    name=_private(c,0x3007,'NUCLETRON',0x16)
                    if name and str(c.ContourGeometricType)=='POINT':
                        key=(int(roi.ReferencedROINumber),int(c.ContourNumber))
                        if key in groups:raise ValueError('Duplicate point-set identifiers in RP.')
                        groups[key]=(set_names.get(key[0],''),str(name),[float(v) for v in c.ContourData])
    points=[];seen=set()
    for x in seq:
        roi=int(x.ReferencedROINumber)
        contour=getattr(contours.get(roi),'ContourSequence',[])
        if not contour or any(str(c.ContourGeometricType)!='POINT' for c in contour):continue
        if roi in seen:raise ValueError('Duplicate RD point dose identifiers.')
        seen.add(roi)
        if str(getattr(x,'DoseUnits',''))!='GY':raise ValueError('Point dose units must be GY; relative doses are not inferred.')
        dose=float(x.DoseValue)
        if not math.isfinite(dose) or dose<0:raise ValueError('Invalid point dose.')
        name=names.get(roi,f'ROI {roi}');group=''
        set_id=_private(x,0x300b,'NUCLETRON',0)
        point_id=_private(x,0x300b,'NUCLETRON',1)
        match=groups.get((int(set_id),int(point_id))) if set_id is not None and point_id is not None else None
        if match:
            group,rp_name,coords=match
            rd_coords=[float(v) for v in contour[0].ContourData]
            if len(rd_coords)!=3 or len(coords)!=3 or max(abs(a-b) for a,b in zip(coords,rd_coords))>.01:
                raise ValueError('RP point-set coordinates do not match the RD point.')
            if rp_name.casefold()!=name.casefold():raise ValueError('RP and RD point names disagree.')
        points.append(dict(roi=roi,name=name,group=group,dose=dose,target=suggest_point(name,group)))
    if not points:raise ValueError('No POINT contours with dose values were found in the RD.')
    return dict(date=_date(rd),file=Path(rd_path).name,points=points)


def read_fraction_dicoms(paths, patient_id):
    """Validate one fraction's files before returning any changes to the course."""
    import pydicom
    from collections import Counter
    files={'RTPLAN':[], 'RTDOSE':[], 'CT':[]}
    patient_id=patient_id.strip()
    for path in dict.fromkeys(map(str,paths)):
        ds=pydicom.dcmread(path,stop_before_pixels=True)
        modality=str(getattr(ds,'Modality',''))
        if modality not in files:raise ValueError('Select RP, RD, or CT DICOM files only.')
        source_id=str(getattr(ds,'PatientID','')).strip()
        if not source_id:raise ValueError('A selected DICOM has no patient ID.')
        patient_id=patient_id or source_id
        if source_id.casefold()!=patient_id.casefold():
            raise ValueError('All selected DICOM files must match the current patient.')
        files[modality].append((path,ds))
    if not any(files.values()):raise ValueError('Select RP, RD, or CT files.')
    if len(files['RTPLAN'])>1 or len(files['RTDOSE'])>1:
        raise ValueError('Select one RP and one RD for this fraction, plus any CT slices.')
    frames={str(ds.FrameOfReferenceUID) for items in files.values() for _,ds in items if getattr(ds,'FrameOfReferenceUID',None)}
    if len(frames)>1:raise ValueError('The selected DICOM files have different frames of reference. Select files from the same plan / CT.')
    result={'ct_date':None,'points':None,'date':'','warnings':[],'patient_id':patient_id}
    result['rp_name']=None;result['rp_date']=''
    if files['RTPLAN']:
        rp_path,rp=files['RTPLAN'][0]
        result['rp_name']=str(getattr(rp,'RTPlanLabel','')).strip() or str(getattr(rp,'RTPlanName','')).strip() or Path(rp_path).name
        raw=str(getattr(rp,'RTPlanDate',''))
        if raw:result['rp_date']=datetime.strptime(raw,'%Y%m%d').date().isoformat()
    if files['CT']:
        dates=set();series=set()
        for _,ds in files['CT']:
            series.add(str(getattr(ds,'SeriesInstanceUID','')))
            raw=str(getattr(ds,'AcquisitionDate','')) or str(getattr(ds,'AcquisitionDateTime',''))[:8]
            if not raw:
                raw=str(getattr(ds,'SeriesDate',''))
                result['warnings'].append('CT acquisition date unavailable; using CT series date.')
            if not raw:raise ValueError('A CT file has no acquisition or series date. No date was inferred.')
            dates.add(datetime.strptime(raw,'%Y%m%d').date().isoformat())
        if len(dates)!=1 or len(series)!=1:
            raise ValueError('Select CT slices from one series and acquisition date for this fraction.')
        result['ct_date']=dates.pop()
    if files['RTDOSE']:
        rd_path,rd=files['RTDOSE'][0]
        rp_path=files['RTPLAN'][0][0] if files['RTPLAN'] else None
        if rp_path:
            rp=files['RTPLAN'][0][1]
            refs=[str(x.ReferencedSOPInstanceUID) for x in getattr(rd,'ReferencedRTPlanSequence',[])]
            if str(rp.SOPInstanceUID) not in refs:raise ValueError('The RD does not reference this RP plan.')
        if getattr(rd,'RTDoseROISequence',None):
            result.update(read_point_doses(rd_path,patient_id,rp_path))
            counts=Counter(p['target'] for p in result['points'] if p['target'])
            for point in result['points']:
                if point['target'] and counts[point['target']]>1:point['target']=None
        else:result['warnings'].append('This RD has no exported point doses; existing points were retained.')
    elif files['RTPLAN']:
        result['warnings'].append('RP loaded without RD: calculated point doses require the RD file.')
    result['warnings']=list(dict.fromkeys(result['warnings']))
    return result
