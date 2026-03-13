#!/usr/bin/env python3
"""
parse_clss_csv.py
─────────────────
Parses a CLSS CSV export for the CCSF Math/Statistics schedule
and writes a `let DATA=[...]` JavaScript block to stdout (or a file).

Usage:
    python3 parse_clss_csv.py input.csv             # prints to stdout
    python3 parse_clss_csv.py input.csv output.js   # writes JS block to file
    python3 parse_clss_csv.py input.csv --inject fa26_schedule.html
        # replaces the let DATA=[...] block inside an existing HTML file

Column indices (0-based) expected in the CLSS export:
    0  – (empty on data rows; course group header rows have content here, col 1 empty)
    1  – CLSS ID          ← used to locate the header row
    2  – CRN
    8  – Course           (e.g. "MATH 110A")
    9  – Section #        (e.g. "70952 (001)")
   10  – Course Title
   12  – Schedule Type    (Lecture / Online Learning / Online Hybrid)
   14  – Meeting Pattern  (e.g. "MW 8:40am-10:55am")
   15  – Meetings         (full string used for dated in-person detection)
   16  – Instructor
   17  – Room
   18  – Status
   19  – Part of Term
   23  – Campus
   26  – Credit Hrs
   29  – Enrollment
   30  – Maximum Enrollment
"""

import csv
import json
import re
import sys
from pathlib import Path

# ── Column indices ────────────────────────────────────────────────────────────
COL_CLSS_ID    =  1
COL_CRN        =  2
COL_COURSE     =  8
COL_SECTION    =  9
COL_TITLE      = 10
COL_SCHED_TYPE = 12
COL_PATTERN    = 14
COL_MEETINGS   = 15
COL_INSTRUCTOR = 16
COL_ROOM       = 17
COL_STATUS     = 18
COL_PART_TERM  = 19
COL_CAMPUS     = 23
COL_CREDITS    = 26
COL_ENROLL     = 29
COL_MAX_ENROLL = 30
COL_NOTES_1    = 43   # Section Notes#1 (often empty)
COL_NOTES_2    = 44   # Section Notes#2 (CityOnline boilerplate etc.)

MONTHS = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
          'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']


# ── CSV parser ────────────────────────────────────────────────────────────────
def parse_csv_file(path: str) -> list[dict]:
    """Read the CSV, locate the header row, and return a list of section dicts."""
    with open(path, newline='', encoding='utf-8-sig') as f:
        raw = list(csv.reader(f))

    # Find the header row (contains 'CLSS ID' in one of its cells)
    hdr_idx = next(
        (i for i, row in enumerate(raw) if any(c == 'CLSS ID' for c in row)),
        None
    )
    if hdr_idx is None:
        raise ValueError("Could not find header row (no cell equals 'CLSS ID')")

    data_rows = raw[hdr_idx + 1:]
    sections = []

    for row in data_rows:
        # Skip blank rows
        if not any(row):
            continue
        # Pad short rows so index access is safe
        while len(row) <= max(COL_MAX_ENROLL, COL_CAMPUS, COL_NOTES_2):
            row.append('')

        # Skip course group header rows: col 0 has content but col 1 is empty
        if row[0].strip() and not row[COL_CLSS_ID].strip():
            continue

        # Skip rows with no CLSS ID (catches any other non-data lines)
        if not row[COL_CLSS_ID].strip():
            continue

        meetings_raw = row[COL_MEETINGS].strip()
        sched_type   = row[COL_SCHED_TYPE].strip()

        sections.append({
            'course':        row[COL_COURSE].strip(),
            'courseTitle':   row[COL_TITLE].strip() or row[COL_SECTION].strip(),
            'crn':           row[COL_CRN].strip(),
            'section':       row[COL_SECTION].strip(),
            'scheduleType':  sched_type,
            'meetingPattern': row[COL_PATTERN].strip(),
            'instructor':    clean_instructor(row[COL_INSTRUCTOR]),
            'room':          row[COL_ROOM].strip(),
            'status':        row[COL_STATUS].strip(),
            'partOfTerm':    row[COL_PART_TERM].strip(),
            'campus':        row[COL_CAMPUS].strip(),
            'credits':       row[COL_CREDITS].strip(),
            'enrollment':    row[COL_ENROLL].strip() or '0',
            'maxEnrollment': row[COL_MAX_ENROLL].strip() or '0',
            'inPersonDates': extract_dates(meetings_raw, sched_type),
            'notes':         clean_notes(row[COL_NOTES_1], row[COL_NOTES_2]),
        })

    return sections


# ── Instructor name cleaning ──────────────────────────────────────────────────
# Raw format examples:
#   "Bradach, Kyle (S00015786) [Primary, 100%]"
#   "Wiggins, Shawn (@00282836) [Primary, 100%]; Wiggins, Shawn (@00282836) [100%]"
#   "Staff [Primary, 100%]"
_ID_BRACKET_RE = re.compile(
    r'\s*\([A-Z@][A-Z0-9]*\d+\)\s*\[.*?\]'  # (S00123) / (@00123) / (WA123) etc. followed by [role]
    r'|\s*\[.*?\]',                           # bare [role] with no ID (e.g. Staff [Primary])
    re.DOTALL
)

def clean_instructor(raw: str) -> str:
    """Strip employee IDs and role brackets; deduplicate semicolon-separated names."""
    cleaned = _ID_BRACKET_RE.sub('', raw).strip()
    parts = [p.strip() for p in cleaned.split(';') if p.strip()]
    unique = list(dict.fromkeys(parts))          # preserves order, deduplicates
    return '; '.join(unique) if unique else 'Staff'


def clean_notes(n1: str, n2: str) -> str:
    """Combine Notes#1 and Notes#2, stripping excess whitespace. Returns '' if both empty."""
    parts = [p.strip() for p in [n1, n2] if p.strip()]
    return ' '.join(parts)

# ── In-person date extraction ─────────────────────────────────────────────────
# Detects two patterns in the Meetings column:
#   Pattern 1 – a timed entry on a specific date:
#     "F 1:10pm-3pm (10/02/2026) [Lecture (Class)]"
#   Pattern 2 – "Does Not Meet" on a specific date (used for some hybrids):
#     "Does Not Meet (10/02/2026) [Lecture (Class)]"
_DATE_P1 = re.compile(
    r'[A-Za-z]+\s+[\d:apm\-]+\s+\((\d{1,2})\/(\d{1,2})\/\d{4}\)'
    r'\s+\[(?:Lecture|Online Hybrid)\s+\(Class\)\]'
)
_DATE_P2 = re.compile(
    r'Does Not Meet\s+\((\d{1,2})\/(\d{1,2})\/\d{4}\)'
    r'\s+\[(?:Lecture|Online Hybrid|Online Learning)\s+\(Class\)\]'
)

def extract_dates(meetings: str, sched_type: str) -> list[str]:
    """
    Return a list of 'Mon DD' strings for dated in-person meetings,
    but only for Online Hybrid sections with 1–6 such dates.
    Returns [] otherwise (including for weekly hybrid patterns).
    """
    if sched_type != 'Online Hybrid':
        return []

    dates = set()
    for m in _DATE_P1.finditer(meetings):
        dates.add(f"{MONTHS[int(m.group(1))]} {int(m.group(2))}")
    for m in _DATE_P2.finditer(meetings):
        dates.add(f"{MONTHS[int(m.group(1))]} {int(m.group(2))}")

    # Only treat as "specific dated meetings" if there are 1–6 of them.
    # More than 6 suggests a regular weekly pattern, not isolated dates.
    return sorted(dates, key=lambda s: s) if 1 <= len(dates) <= 6 else []


# ── JS output ─────────────────────────────────────────────────────────────────
def to_js_block(sections: list[dict]) -> str:
    """Serialize the section list to a `let DATA=[...];` JS assignment."""
    json_str = json.dumps(sections, ensure_ascii=False, separators=(',', ':'))
    return f'let DATA={json_str};\n'


# ── HTML injection ────────────────────────────────────────────────────────────
_DATA_BLOCK_RE = re.compile(r'let DATA=\[.*?\];', re.DOTALL)

def inject_into_html(html_path: str, js_block: str) -> None:
    """Replace the existing `let DATA=[...];` block inside an HTML file."""
    html = Path(html_path).read_text(encoding='utf-8')
    if not _DATA_BLOCK_RE.search(html):
        raise ValueError(f"No `let DATA=[...];` block found in {html_path}")
    updated = _DATA_BLOCK_RE.sub(js_block.rstrip('\n'), html, count=1)
    Path(html_path).write_text(updated, encoding='utf-8')
    print(f"✓ Injected {len(sections)} sections into {html_path}", file=sys.stderr)


# ── CLI entry point ───────────────────────────────────────────────────────────
if __name__ == '__main__':
    args = sys.argv[1:]

    if not args:
        print(__doc__)
        sys.exit(0)

    csv_path = args[0]
    sections = parse_csv_file(csv_path)
    js_block = to_js_block(sections)

    print(f"✓ Parsed {len(sections)} sections from {csv_path}", file=sys.stderr)

    if len(args) >= 3 and args[1] == '--inject':
        # python3 parse_clss_csv.py input.csv --inject fa26_schedule.html
        inject_into_html(args[2], js_block)

    elif len(args) >= 2:
        # python3 parse_clss_csv.py input.csv output.js
        Path(args[1]).write_text(js_block, encoding='utf-8')
        print(f"✓ Wrote DATA block to {args[1]}", file=sys.stderr)

    else:
        # python3 parse_clss_csv.py input.csv  → stdout
        print(js_block, end='')
