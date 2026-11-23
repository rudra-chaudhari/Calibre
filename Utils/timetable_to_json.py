import argparse
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path

from openpyxl import load_workbook

TIME_RANGE_RE = re.compile(
    r"(\d{1,2})[:.](\d{2})(?:[:.]\d{2})?\s*([ap]m)?\s*(?:-|\u2013|\u2014|to)\s*"
    r"(\d{1,2})[:.](\d{2})(?:[:.]\d{2})?\s*([ap]m)?",
    re.I,
)
DAY_RE = re.compile(
    r"^\W*\d*\W*(mon(?:day)?|tue(?:s(?:day)?)?|wed(?:nesday)?|thu(?:r(?:s(?:day)?)?)?"
    r"|fri(?:day)?|sat(?:urday)?|sun(?:day)?)\b",
    re.I,
)
DAYS = {
    "mon": (1, "Mon", "Monday"),
    "tue": (2, "Tue", "Tuesday"),
    "wed": (3, "Wed", "Wednesday"),
    "thu": (4, "Thu", "Thursday"),
    "fri": (5, "Fri", "Friday"),
    "sat": (6, "Sat", "Saturday"),
    "sun": (7, "Sun", "Sunday"),
}
COURSE_RE = re.compile(
    r"^(?P<dept>[A-Z]{1,6})\s*-?\s*(?P<num>\d{2,5}[A-Z]{0,2}(?:\.\d+)?)"
    r"\s*(?:\(\s*(?P<sec>[^)]*?)\s*\))?\s*(?P<title>.*)$"
)
ROOM_BRACKET_RE = re.compile(r"^\[(.*)\]$")
ROOM_PREFIX_RE = re.compile(r"^(?:class\s*room|classroom|room|venue)\s*:\s*(.*)$", re.I)
SECTION_SPLIT_RE = re.compile(r"[\s,;/]+")
EXCEL_SUFFIXES = {".xlsx", ".xlsm"}
MAX_HEADER_SCAN = 15


def clean(value):
    return str(value).replace("\xa0", " ").replace("\r", "")


def squeeze(text):
    return re.sub(r"\s+", " ", text).strip()


def to_minutes(hour, minute, meridiem):
    h, m = int(hour), int(minute)
    if m > 59:
        return None
    if meridiem:
        if not 1 <= h <= 12:
            return None
        h = h % 12 + (12 if meridiem.lower() == "pm" else 0)
    elif h > 23:
        return None
    return h * 60 + m


def format_minutes(total):
    return f"{total // 60:02d}:{total % 60:02d}"


def parse_time_range(value):
    if value is None:
        return None
    match = TIME_RANGE_RE.search(clean(value))
    if not match:
        return None
    h1, m1, p1, h2, m2, p2 = match.groups()
    start = to_minutes(h1, m1, p1 or p2)
    end = to_minutes(h2, m2, p2)
    if start is None or end is None:
        return None
    if p2 and not p1 and start >= end and start >= 720:
        start -= 720
    if end <= start:
        return None
    return format_minutes(start), format_minutes(end)


def parse_day(value):
    if value is None:
        return None
    text = clean(value).strip()
    if len(text) > 25:
        return None
    match = DAY_RE.match(text)
    if not match:
        return None
    return DAYS[match.group(1)[:3].lower()]


def split_section(raw):
    if not raw:
        return None, None
    tokens = [token for token in SECTION_SPLIT_RE.split(raw.strip()) if token]
    marker = "M" if "M" in tokens else None
    rest = " ".join(token for token in tokens if token != "M")
    return rest or None, marker


def extract_room(line):
    bracket = ROOM_BRACKET_RE.match(line)
    if bracket:
        text = bracket.group(1).strip()
        prefixed = ROOM_PREFIX_RE.match(text)
        return squeeze(prefixed.group(1) if prefixed else text)
    prefixed = ROOM_PREFIX_RE.match(line)
    if prefixed:
        return squeeze(prefixed.group(1))
    return None


def new_block(header):
    return {"header": header, "room": None, "people": []}


def build_course(block):
    header = block["header"]
    instructor = ", ".join(block["people"]) or None
    room = block["room"] or None
    if header is None:
        if instructor is None and room is None:
            return None
        return {
            "department": None,
            "course_code": None,
            "section": None,
            "marker": None,
            "title": None,
            "room": room,
            "instructor": instructor,
            "raw": instructor,
        }
    department = header.group("dept").upper()
    section, marker = split_section(header.group("sec"))
    return {
        "department": department,
        "course_code": f"{department} {header.group('num')}",
        "section": section,
        "marker": marker,
        "title": squeeze(header.group("title") or "") or None,
        "room": room,
        "instructor": instructor,
    }


def parse_cell(value):
    if value is None:
        return []
    text = clean(value).strip()
    if not text:
        return []
    blocks = []
    current = None
    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        room = extract_room(line)
        if room is not None:
            if current is None:
                current = new_block(None)
                blocks.append(current)
            current["room"] = room
            continue
        header = COURSE_RE.match(line)
        if header:
            if current is not None and current["header"] is None and not current["people"]:
                current["header"] = header
            else:
                current = new_block(header)
                blocks.append(current)
            continue
        if current is None:
            current = new_block(None)
            blocks.append(current)
        current["people"].append(squeeze(line))
    return [course for course in map(build_course, blocks) if course is not None]


def sheet_to_grid(ws):
    rows = [list(row) for row in ws.iter_rows(values_only=True)]
    width = max((len(row) for row in rows), default=0)
    grid = [row + [None] * (width - len(row)) for row in rows]
    last_row, last_col = len(grid) - 1, width - 1
    merges = []
    for rng in ws.merged_cells.ranges:
        r1, c1 = rng.min_row - 1, rng.min_col - 1
        if r1 > last_row or c1 > last_col:
            continue
        merges.append((r1, c1, min(rng.max_row - 1, last_row), min(rng.max_col - 1, last_col)))
    return grid, merges


def transpose(grid, merges):
    if not grid:
        return grid, merges
    transposed = [list(row) for row in zip(*grid)]
    return transposed, [(c1, r1, c2, r2) for (r1, c1, r2, c2) in merges]


def find_time_header(grid):
    best = None
    for index, row in enumerate(grid[:MAX_HEADER_SCAN]):
        slots = {}
        for col, value in enumerate(row):
            parsed = parse_time_range(value)
            if parsed:
                slots[col] = parsed
        if len(slots) >= 2 and (best is None or len(slots) > len(best[1])):
            best = (index, slots)
    return best


def detect_layout(grid, merges):
    header = find_time_header(grid)
    if header:
        return grid, merges, header[0], header[1]
    grid, merges = transpose(grid, merges)
    header = find_time_header(grid)
    if header:
        return grid, merges, header[0], header[1]
    return None


def find_day_column(grid, header_row):
    width = max((len(row) for row in grid), default=0)
    best_col, best_count = None, 0
    for col in range(width):
        count = sum(1 for r in range(header_row + 1, len(grid)) if parse_day(grid[r][col]))
        if count > best_count:
            best_col, best_count = col, count
    return best_col


def build_spans(merges):
    spans = {}
    for r1, c1, r2, c2 in merges:
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                spans[(r, c)] = (r1, c1, r2, c2)
    return spans


def convert_sheet(ws):
    grid, merges = sheet_to_grid(ws)
    layout = detect_layout(grid, merges)
    if layout is None:
        return None
    grid, merges, header_row, slots = layout
    day_col = find_day_column(grid, header_row)
    if day_col is None:
        return None
    spans = build_spans(merges)
    slot_cols = sorted(slots)
    entries = []
    for r in range(header_row + 1, len(grid)):
        day_span = spans.get((r, day_col))
        day_value = grid[day_span[0]][day_span[1]] if day_span else grid[r][day_col]
        day = parse_day(day_value)
        if day is None:
            continue
        day_no, day_short, day_full = day
        for c in slot_cols:
            span = spans.get((r, c))
            if span and c != span[1]:
                continue
            value = grid[span[0]][span[1]] if span else grid[r][c]
            courses = parse_cell(value)
            if not courses:
                continue
            last_col = span[3] if span else c
            end_col = max((col for col in slot_cols if c <= col <= last_col), default=c)
            for course in courses:
                entries.append(
                    {
                        "day": day_short,
                        "day_name": day_full,
                        "day_no": day_no,
                        "start_time": slots[c][0],
                        "end_time": slots[end_col][1],
                        **course,
                    }
                )
    return entries


def rooms_compatible(first, second):
    return first is None or second is None or first == second


def merge_group(items):
    unique = []
    for item in items:
        for kept in unique:
            if kept["section"] == item["section"] and kept["room"] == item["room"]:
                kept["marker"] = kept["marker"] or item["marker"]
                break
        else:
            unique.append(dict(item))
    result = list(unique)
    for entry in unique:
        if entry["marker"] is None or entry["section"] is not None:
            continue
        candidates = [
            other
            for other in result
            if other is not entry
            and other["marker"] is None
            and rooms_compatible(entry["room"], other["room"])
        ]
        if len(candidates) > 1 and entry["room"] is not None:
            candidates = [other for other in candidates if other["room"] == entry["room"]]
        if len(candidates) == 1:
            target = candidates[0]
            target["room"] = target["room"] or entry["room"]
            target["marker"] = entry["marker"]
            result = [other for other in result if other is not entry]
    return result


def dedupe(entries):
    groups = OrderedDict()
    for entry in entries:
        key = (
            entry["day_no"],
            entry["start_time"],
            entry["end_time"],
            entry["course_code"],
            entry["instructor"],
            entry.get("raw"),
        )
        groups.setdefault(key, []).append(entry)
    merged = []
    for items in groups.values():
        merged.extend(merge_group(items))
    return merged


def sort_key(entry):
    return (
        entry["day_no"],
        entry["start_time"],
        entry["end_time"],
        entry["course_code"] or "",
        entry["section"] or "",
        entry["room"] or "",
        entry["instructor"] or "",
    )


def shape(entries, fmt):
    ordered = sorted(entries, key=sort_key)
    if fmt == "day":
        grouped = {}
        for entry in ordered:
            trimmed = {k: v for k, v in entry.items() if k not in ("day", "day_name", "day_no")}
            grouped.setdefault(entry["day"], []).append(trimmed)
        return grouped
    if fmt == "course":
        grouped = {}
        for entry in ordered:
            trimmed = {k: v for k, v in entry.items() if k not in ("course_code", "department")}
            grouped.setdefault(entry["course_code"] or "UNKNOWN", []).append(trimmed)
        return grouped
    return ordered


def parse_departments(value):
    if not value:
        return None
    names = {part.strip().upper() for part in value.split(",") if part.strip()}
    return names or None


def process_file(path, departments):
    workbook = load_workbook(path, data_only=True)
    try:
        sheets = OrderedDict()
        for ws in workbook.worksheets:
            entries = convert_sheet(ws)
            if entries is None:
                print(f"   [skip] sheet '{ws.title}': no timetable structure found", file=sys.stderr)
                continue
            if departments:
                entries = [e for e in entries if (e["department"] or "") in departments]
            sheets[ws.title] = dedupe(entries)
        return sheets
    finally:
        workbook.close()


def build_result(path, sheets, fmt):
    shaped = {name: shape(entries, fmt) for name, entries in sheets.items()}
    result = {"source_file": Path(path).name, "format": fmt}
    if len(shaped) == 1:
        result["timetable"] = next(iter(shaped.values()))
    else:
        result["sheets"] = shaped
    return result


def collect_inputs(items):
    files, seen = [], set()
    for item in items:
        path = Path(item)
        if path.is_dir():
            found = sorted(
                p
                for p in path.iterdir()
                if p.is_file()
                and p.suffix.lower() in EXCEL_SUFFIXES
                and not p.name.startswith(("~$", "."))
            )
        elif path.is_file():
            found = [path]
        else:
            print(f"[warn] not found: {item}", file=sys.stderr)
            continue
        for p in found:
            resolved = p.resolve()
            if resolved not in seen:
                seen.add(resolved)
                files.append(p)
    return files


def write_json(path, payload):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def build_parser():
    parser = argparse.ArgumentParser(description="Convert timetable Excel files to JSON")
    parser.add_argument("inputs", nargs="+", help="one or more .xlsx files or folders")
    parser.add_argument("-o", "--output", help="output path (single input file only)")
    parser.add_argument("--merge", metavar="OUT.json", help="write all inputs into one combined JSON file")
    parser.add_argument("--format", choices=["flat", "day", "course"], default="flat")
    parser.add_argument("--dept", help="comma separated department codes to keep, for example CS,EE,MA")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    if args.output and args.merge:
        parser.error("-o and --merge cannot be used together")
    files = collect_inputs(args.inputs)
    if not files:
        sys.exit("No input files found")
    if args.output and len(files) > 1:
        parser.error("-o accepts a single input file; use --merge for multiple files")
    departments = parse_departments(args.dept)

    failures = 0
    merged, loaded = [], []
    for path in files:
        try:
            sheets = process_file(path, departments)
        except Exception as error:
            failures += 1
            print(f"[error] {path.name}: {error}", file=sys.stderr)
            continue
        total = sum(len(entries) for entries in sheets.values())
        if args.merge:
            loaded.append(path.name)
            for entries in sheets.values():
                merged.extend(entries)
            print(f"[ok] {path.name}: {total} entries")
            continue
        target = Path(args.output) if args.output else path.with_suffix(".json")
        write_json(target, build_result(path, sheets, args.format))
        print(f"[ok] {path.name} -> {target} ({total} entries)")

    if args.merge:
        combined = dedupe(merged)
        payload = {
            "source_files": loaded,
            "format": args.format,
            "timetable": shape(combined, args.format),
        }
        write_json(args.merge, payload)
        print(f"[ok] merged -> {args.merge} ({len(combined)} entries)")

    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
