"""Calculation and course state ported from the supplied MATLAB dashboard.

No GUI or third-party dependencies. Fractions use zero-based indexes internally.
"""
from dataclasses import dataclass, field
from pathlib import Path
import math
import re


@dataclass(frozen=True)
class Metric:
    key: str
    label: str
    row: int
    ab: int = 0
    goal: str = ''
    hard: str = ''


# Workbook physical rows; each dose's EQD2 row is the following row.
STRUCTURES = (
    ('GTV_res', 'gtvres', (Metric('volume', 'Volume [cc]', 38), Metric('D98', 'D98 [Gy]', 39, 10, '>95', '>90'))),
    ('CTV_HR', 'ctvhr', (Metric('volume', 'Volume [cc]', 42), Metric('D98', 'D98 [Gy]', 43, 10, '>75', '>75'), Metric('D90', 'D90 [Gy]', 45, 10, '90-95', '>85'), Metric('D50', 'D50 [Gy]', 47, 10))),
    ('CTV_IR', 'ctvir', (Metric('volume', 'Volume [cc]', 50), Metric('D98', 'D98 [Gy]', 51, 10, '>60', '>60'), Metric('D90', 'D90 [Gy]', 53, 10))),
    ('BLADDER', 'bladder', (Metric('volume', 'Volume [cc]', 56), Metric('D0p1', 'D0.1cc [Gy]', 59, 3), Metric('D2', 'D2cc [Gy]', 61, 3, '<80', '<90'))),
    ('RECTUM', 'rectum', (Metric('volume', 'Volume [cc]', 64), Metric('D0p1', 'D0.1cc [Gy]', 67, 3), Metric('D2', 'D2cc [Gy]', 69, 3, '<65', '<75'))),
    ('SIGMOID', 'sigmoid', (Metric('volume', 'Volume [cc]', 72), Metric('D0p1', 'D0.1cc [Gy]', 73, 3), Metric('D2', 'D2cc [Gy]', 75, 3, '<70', '<75'))),
    ('INTESTINES OR BOWEL', 'bowel', (Metric('volume', 'Volume [cc]', 78), Metric('D0p1', 'D0.1cc [Gy]', 79, 3), Metric('D2', 'D2cc [Gy]', 81, 3, '<70', '<75'))),
)
METRICS = {f'{key}_{m.key}': m for _, key, metrics in STRUCTURES for m in metrics}


def number(value):
    if value is None or str(value).strip() == '':
        return None
    n = float(value)
    if not math.isfinite(n):
        raise ValueError('Enter a finite number.')
    return float(f'{n:.2f}')


def fmt(value):
    return '' if value is None else f'{value:.1f}'


def eqd2(dose, ab):
    return dose * (1 + dose / ab) / (1 + 2 / ab)


def meets(value, constraint):
    if not constraint:
        return False
    match = re.fullmatch(r'([\d.]+)-([\d.]+)', constraint)
    if match:
        return float(match[1]) <= value <= float(match[2])
    match = re.fullmatch(r'([<>]=?)([\d.]+)', constraint)
    if not match:
        return False
    op, threshold = match[1], float(match[2])
    return {'>': value > threshold, '>=': value >= threshold,
            '<': value < threshold, '<=': value <= threshold}[op]


def status(value, metric):
    if value is None or not (metric.goal or metric.hard):
        return 'neutral'
    value = number(value)  # MATLAB evaluates the displayed total.
    if meets(value, metric.goal):
        return 'pass'
    if meets(value, metric.hard):
        return 'warn'
    return 'fail'


def structure_key(name):
    name = re.sub(r'[ _-]*fx[1-6]\s*$', '', name.strip().lower())
    name = re.sub('[^a-z0-9]', '', name)
    for _, key, _ in STRUCTURES:
        if key in name or (key == 'bowel' and 'intestin' in name):
            return key
    return None


def dose_at_volume(rows, target):
    rows = sorted((d, v) for d, v in rows if math.isfinite(d) and math.isfinite(v))
    if not rows:
        return None
    for (d1, v1), (d2, v2) in zip(rows, rows[1:]):
        if min(v1, v2) <= target <= max(v1, v2):
            return d1 if abs(v2-v1) < 2.220446049250313e-16 else d1 + (target-v1)/(v2-v1)*(d2-d1)
    return min(rows, key=lambda pair: abs(pair[1]-target))[0]


@dataclass
class DVH:
    patient: str
    patient_id: str
    plan: str
    metrics: dict
    ignored: list


def parse_dvh(path):
    raw = Path(path).read_bytes()
    text = raw.decode('utf-16' if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig')
    units = re.search(r'Absolute Dose\s*-\s*\[(cGy|Gy)\]', text, re.I)
    if not units:
        raise ValueError('Expected Absolute Dose - [cGy] or Absolute Dose - [Gy].')
    if not re.search(r'Cumulative mode', text, re.I):
        raise ValueError('This app expects a cumulative DVH export.')
    if re.search(r'(?:Relative Volume|Volume\s*-?\s*\[%\])', text, re.I):
        raise ValueError('Absolute cumulative volume in cc is required, not percent volume.')
    scale = .01 if units[1].lower() == 'cgy' else 1
    def header(key):
        match = re.search(r'^\s*' + re.escape(key) + r':[ \t]*(.*)$', text, re.M)
        return match[1].strip() if match else ''
    parts = re.split(r'^[ \t]*ROI:[ \t]*(.+?)[ \t]*\r?$', text, flags=re.M)
    if len(parts) == 1:
        raise ValueError('No ROI sections were found.')
    metrics, ignored = {}, []
    numeric = r'([-+]?\d*\.?\d+(?:[Ee][-+]?\d+)?)'
    for name, body in zip(parts[1::2], parts[2::2]):
        key = structure_key(name)
        rows = [(float(d)*scale, float(v)) for d, v in re.findall(r'^\s*\d+\s+'+numeric+r'\s+'+numeric+r'\s*$', body, re.M)]
        rows = [(d, v) for d, v in rows if math.isfinite(d) and math.isfinite(v)]
        if not key or not rows:
            ignored.append(name.strip())
            continue
        total = max(v for _, v in rows)
        for _, structure, definitions in STRUCTURES:
            if structure != key:
                continue
            for m in definitions:
                if m.key == 'volume':
                    value = total
                else:
                    target = total*float(m.key[1:])/100 if m.ab == 10 else (.1 if m.key == 'D0p1' else 2)
                    value = dose_at_volume(rows, target)
                metrics[f'{key}_{m.key}'] = number(value)
    if not metrics:
        raise ValueError('No recognized EMBRACE-2 structures with numeric DVH data were found.')
    return DVH(header('Patient'), header('Patient Id'), header('Plan'), metrics, ignored)


@dataclass
class Course:
    count: int = 4
    dose_per_fx: float = 1.8
    prior_fractions: int = 25
    patient: str = ''
    patient_id: str = ''
    values: list = field(default_factory=lambda: [{} for _ in range(5)])
    files: list = field(default_factory=lambda: ['']*5)
    plans: list = field(default_factory=lambda: ['']*5)
    explicit: list = field(default_factory=lambda: [False]*5)

    def baseline(self, ab):
        return self.prior_fractions * eqd2(self.dose_per_fx, ab)

    def total(self, key):
        doses = [v[key] for v in self.values[:self.count] if v.get(key) is not None]
        return sum(eqd2(d, METRICS[key].ab) for d in doses) + self.baseline(METRICS[key].ab) if doses else None

    def edit(self, fx, key, value):
        if not 0 <= fx < self.count or key not in METRICS:
            raise ValueError('This cell is not editable.')
        self.values[fx][key] = number(value)

    def set_prior(self, dose, count):
        d, n = float(dose), float(count)
        if not math.isfinite(d) or not math.isfinite(n) or min(d, n) < 0:
            raise ValueError('Prior radiation values must be finite and nonnegative.')
        self.dose_per_fx, self.prior_fractions = number(d), math.floor(n+.5)

    def copy(self, src, dest):
        self.values[dest] = self.values[src].copy()
        self.plans[dest] = self.plans[src]
        self.files[dest] = re.sub(r' \(carried from Fx\d+\)$', '', self.files[src]) + f' (carried from Fx{src+1})'

    def set_count(self, count):
        if count not in (3, 4, 5):
            raise ValueError('Choose 3, 4, or 5 fractions.')
        old = self.count
        if count < old:
            for fx in range(count, 5):
                self.values[fx] = {}
                self.files[fx] = self.plans[fx] = ''
                self.explicit[fx] = False
        elif count > old:
            sources = [i for i in range(old) if self.explicit[i]]
            if sources:
                for fx in range(old, count):
                    self.copy(sources[-1], fx)
        self.count = count

    def load(self, fx, path):
        if not 0 <= fx < self.count:
            raise ValueError('Inactive fraction.')
        parsed = parse_dvh(path)
        # Validate both fields before changing any state.
        for label, current, new in [('Patient', self.patient, parsed.patient), ('Patient ID', self.patient_id, parsed.patient_id)]:
            if current and new and current.casefold() != new.casefold():
                raise ValueError(f'{label} mismatch: loaded {new}; dashboard {current}.')
        self.patient = self.patient or parsed.patient
        self.patient_id = self.patient_id or parsed.patient_id
        self.explicit[fx] = True
        for dest in range(fx, self.count):
            if dest == fx or not self.explicit[dest]:
                # MATLAB preserves existing metrics absent from the new file.
                self.values[dest].update(parsed.metrics)
                self.plans[dest] = parsed.plan
                self.files[dest] = Path(path).name + (f' (carried from Fx{fx+1})' if dest != fx else '')
        return parsed


@dataclass
class PlanComparison:
    """Four independent single-DVH scenarios using the course's prior RT and N."""
    plans: list = field(default_factory=lambda: [None]*4)
    files: list = field(default_factory=lambda: ['']*4)

    def load(self, slot, path, course):
        if not 0 <= slot < 4:
            raise ValueError('Choose plan 1 through 4.')
        parsed = parse_dvh(path)
        others = [plan for i, plan in enumerate(self.plans) if plan is not None and i != slot]
        references = [(course.patient, course.patient_id)] + [(p.patient, p.patient_id) for p in others]
        for patient, patient_id in references:
            for label, current, new in [('Patient', patient, parsed.patient), ('Patient ID', patient_id, parsed.patient_id)]:
                if current and new and current.casefold() != new.casefold():
                    raise ValueError(f'{label} mismatch: loaded {new}; comparison {current}.')
        self.plans[slot] = parsed
        self.files[slot] = Path(path).name
        return parsed

    def scenario(self, slot, course):
        parsed = self.plans[slot]
        if parsed is None:
            return None
        scenario = Course(count=course.count, dose_per_fx=course.dose_per_fx,
                          prior_fractions=course.prior_fractions,
                          patient=parsed.patient, patient_id=parsed.patient_id)
        for fx in range(course.count):
            scenario.values[fx] = parsed.metrics.copy()
            scenario.plans[fx] = parsed.plan
            scenario.files[fx] = self.files[slot] + ' (repeated scenario)'
        return scenario

    def clear(self, slot):
        self.plans[slot] = None
        self.files[slot] = ''
