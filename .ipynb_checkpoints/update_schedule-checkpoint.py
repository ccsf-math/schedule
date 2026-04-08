#!/usr/bin/env python3
"""
update_schedule.py
Usage: python3 update_schedule.py  input.csv  schedule.html
Reads the CLSS CSV export, parses it, and replaces the let DATA=[...] block in the HTML.
"""
import csv, json, re, sys
from pathlib import Path

COL_CLSS_ID=1; COL_CRN=2; COL_COURSE=8; COL_SECTION=9; COL_TITLE=10
COL_SCHED_TYPE=12; COL_PATTERN=14; COL_MEETINGS=15; COL_INSTRUCTOR=16
COL_ROOM=17; COL_STATUS=18; COL_PART_TERM=19; COL_CAMPUS=23
COL_CREDITS=26; COL_ENROLL=29; COL_MAX_ENROLL=30
COL_NOTE1=43; COL_NOTE2=44

MONTHS=['','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

_ID_RE  = re.compile(r'\s*\([A-Z@][A-Z0-9]*\d+\)\s*\[.*?\]|\s*\[.*?\]', re.DOTALL)
_DATE1  = re.compile(r'[A-Za-z]+\s+[\d:apm\-]+\s+\((\d{1,2})\/(\d{1,2})\/\d{4}\)\s+\[(?:Lecture|Online Hybrid)\s+\(Class\)\]')
_DATE2  = re.compile(r'Does Not Meet\s+\((\d{1,2})\/(\d{1,2})\/\d{4}\)\s+\[(?:Lecture|Online Hybrid|Online Learning)\s+\(Class\)\]')
_DATARE = re.compile(r'let DATA=\[.*?\];', re.DOTALL)

def clean_instructor(raw):
    cleaned = _ID_RE.sub('', raw).strip()
    parts   = [p.strip() for p in cleaned.split(';') if p.strip()]
    return '; '.join(list(dict.fromkeys(parts))) or 'Staff'

def extract_dates(meetings, sched_type):
    if sched_type != 'Online Hybrid': return []
    dates = set()
    for m in _DATE1.finditer(meetings): dates.add(f"{MONTHS[int(m.group(1))]} {int(m.group(2))}")
    for m in _DATE2.finditer(meetings): dates.add(f"{MONTHS[int(m.group(1))]} {int(m.group(2))}")
    return sorted(dates) if 1 <= len(dates) <= 6 else []

def extract_notes(row):
    """Combine Section Notes#1 (col 43) and Notes#2 (col 44); return '' if both blank."""
    n1 = row[COL_NOTE1].strip() if len(row) > COL_NOTE1 else ''
    n2 = row[COL_NOTE2].strip() if len(row) > COL_NOTE2 else ''
    parts = [n for n in [n1, n2] if n]
    return ' '.join(parts)

csv_path  = Path(sys.argv[1])
html_path = Path(sys.argv[2])

with open(csv_path, newline='', encoding='utf-8-sig') as f:
    raw = list(csv.reader(f))

hdr = next((i for i, r in enumerate(raw) if any(c == 'CLSS ID' for c in r)), None)
if hdr is None: sys.exit("ERROR: Could not find header row in CSV")

sections = []
for row in raw[hdr+1:]:
    if not any(row): continue
    while len(row) <= COL_NOTE2: row.append('')
    if row[0].strip() and not row[COL_CLSS_ID].strip(): continue
    if not row[COL_CLSS_ID].strip(): continue
    mt, st = row[COL_MEETINGS].strip(), row[COL_SCHED_TYPE].strip()
    sections.append({
        'course':         row[COL_COURSE].strip(),
        'courseTitle':    row[COL_TITLE].strip() or row[COL_SECTION].strip(),
        'crn':            row[COL_CRN].strip(),
        'section':        row[COL_SECTION].strip(),
        'scheduleType':   st,
        'meetingPattern': row[COL_PATTERN].strip(),
        'instructor':     clean_instructor(row[COL_INSTRUCTOR]),
        'room':           row[COL_ROOM].strip(),
        'status':         row[COL_STATUS].strip(),
        'partOfTerm':     row[COL_PART_TERM].strip(),
        'campus':         row[COL_CAMPUS].strip(),
        'credits':        row[COL_CREDITS].strip(),
        'enrollment':     row[COL_ENROLL].strip() or '0',
        'maxEnrollment':  row[COL_MAX_ENROLL].strip() or '0',
        'inPersonDates':  extract_dates(mt, st),
        'sectionNotes':   extract_notes(row),
    })

js      = 'let DATA=' + json.dumps(sections, ensure_ascii=False, separators=(',',':')) + ';'
html    = html_path.read_text(encoding='utf-8')
updated = _DATARE.sub(js, html, count=1)
html_path.write_text(updated, encoding='utf-8')

n_notes = sum(1 for s in sections if s['sectionNotes'])
print(f"Done: {len(sections)} sections, {len(set(s['course'] for s in sections))} courses, {n_notes} with notes → {html_path.name}")
