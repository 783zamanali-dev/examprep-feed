"""Builds app/src/main/assets/pastpapers.js from the spreadsheets in branding/past-papers/.

Usage:
  build_past_papers.py              check every sheet and write pastpapers.js
  build_past_papers.py --template   write a blank past-papers/TEMPLATE.xlsx to fill in

One row per question, columns:
  Board | Year | Position | Grade | Subject | Question | Option A | Option B | Option C |
  Option D | Answer | Explanation | Difficulty
Board, Year, Position and Grade may be left blank to repeat the row above, so a
paper only needs them on its first row. Difficulty is optional: the grade sets it
(BPS 10-14 easy, 15-16 medium, 17 and up hard).
Nothing is written if any row has a problem, so a half-broken paper never ships.
Only the standard library is used, so it runs without installing anything."""
import csv
import json
import pathlib
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent
SRC = ROOT / "past-papers"
OUT = ROOT.parent / "app" / "src" / "main" / "assets" / "pastpapers.js"

COLUMNS = ["Board", "Year", "Position", "Grade", "Subject", "Question", "Option A", "Option B",
           "Option C", "Option D", "Answer", "Explanation", "Difficulty"]
BOARDS = ["FIA", "MOD", "FPSC", "KPSC", "SPSC", "PPSC", "BPSC", "AJK", "GB", "NTS", "PMS", "PCS",
          "PTS", "OTS"]
# Same keys and aliases as PP_SUBJECTS / PP_ALIASES in index.html — change both together
SUBJECTS = {
    "english": "English", "urdu": "Urdu", "maths": "Mathematics",
    "everyday_science": "General Science", "general_knowledge": "General Knowledge",
    "current_affairs": "Current Affairs", "pakistan_affairs": "Pakistan Affairs",
    "islamiyat": "Islamic Studies", "psychological": "Logical Reasoning",
    "computer": "Computer", "other": "Other",
}
ALIASES = {
    "english": "english", "eng": "english", "urdu": "urdu",
    "mathematics": "maths", "maths": "maths", "math": "maths", "arithmetic": "maths",
    "quantitative": "maths", "quant": "maths",
    "generalscience": "everyday_science", "everydayscience": "everyday_science",
    "science": "everyday_science", "gs": "everyday_science", "eds": "everyday_science",
    "generalknowledge": "general_knowledge", "gk": "general_knowledge",
    "currentaffairs": "current_affairs", "ca": "current_affairs",
    "pakistanaffairs": "pakistan_affairs", "pakaffairs": "pakistan_affairs",
    "pakistanstudies": "pakistan_affairs", "pakstudies": "pakistan_affairs",
    "islamicstudies": "islamiyat", "islamiyat": "islamiyat", "islamiat": "islamiyat",
    "islamic": "islamiyat",
    "logicalreasoning": "psychological", "reasoning": "psychological", "iq": "psychological",
    "intelligence": "psychological", "analytical": "psychological",
    "computer": "computer", "computerscience": "computer", "it": "computer", "cs": "computer",
    "other": "other",
}
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def xlsx_sheet_count(path):
    with zipfile.ZipFile(path) as z:
        return sum(1 for n in z.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", n))


def read_xlsx(path, index=0):
    """The grid of one worksheet (the first by default; index counts sheet1, sheet2, ...)."""
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS):
                shared.append("".join(t.text or "" for t in si.iter(f"{{{NS['m']}}}t")))
        sheet = sorted((n for n in z.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", n)),
                       key=lambda n: int(re.search(r"(\d+)\.xml$", n).group(1)))[index]
        grid = []
        for row in ET.fromstring(z.read(sheet)).iter(f"{{{NS['m']}}}row"):
            cells = {}
            for c in row.findall("m:c", NS):
                col = re.match(r"[A-Z]+", c.get("r", "A")).group()
                ci = 0
                for ch in col:
                    ci = ci * 26 + ord(ch) - 64
                t = c.get("t")
                if t == "inlineStr":
                    v = "".join(x.text or "" for x in c.iter(f"{{{NS['m']}}}t"))
                else:
                    vn = c.find("m:v", NS)
                    v = vn.text if vn is not None else ""
                    if t == "s":
                        v = shared[int(v)]
                cells[ci - 1] = str(v or "").strip()
            if cells:
                grid.append([cells.get(i, "") for i in range(max(cells) + 1)])
    return grid


def read_rows(path):
    if path.suffix.lower() == ".csv":
        with open(path, encoding="utf-8-sig", newline="") as f:
            grid = [r for r in csv.reader(f)]
    else:
        grid = read_xlsx(path)
    grid = [r for r in grid if any(str(c).strip() for c in r)]
    if not grid:
        return []
    head = [norm(h) for h in grid[0]]
    return [{h: (r[i].strip() if i < len(r) else "") for i, h in enumerate(head) if h}
            for r in grid[1:]]


def pick(row, *names):
    for n in names:
        v = row.get(norm(n), "")
        if v:
            return v
    return ""


def level(text):
    s = str(text).lower()
    if re.search(r"easy", s):
        return "Easy"
    if re.search(r"med", s):
        return "Medium"
    if re.search(r"hard", s):
        return "Hard"
    m = re.search(r"\d+", s)
    if not m:
        return ""
    n = int(m.group())
    return "Easy" if n <= 14 else "Medium" if n <= 16 else "Hard"


def answer(raw, opts):
    s = raw.strip().upper()
    if re.fullmatch(r"[ABCD]", s):
        return "ABCD".index(s)
    if re.fullmatch(r"[1-4]", s):
        return int(s) - 1
    for i, o in enumerate(opts):
        if o and o.lower() == raw.strip().lower():
            return i
    return -1


def slug(*parts):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", " ".join(map(str, parts)).lower())).strip("-")


def build():
    files = sorted(p for p in SRC.glob("*") if p.suffix.lower() in (".xlsx", ".csv")
                   and not p.name.startswith(("_", "~", "TEMPLATE")))
    papers, errors, ids = {}, [], set()
    for f in files:
        carry = {}
        for i, row in enumerate(read_rows(f), start=2):
            where = f"{f.name} row {i}"
            for key, names in (("board", ("Board",)), ("year", ("Year",)),
                               ("post", ("Position", "Post")), ("bps", ("Grade", "BPS", "Scale"))):
                v = pick(row, *names)
                if v:
                    carry[key] = v
            board = carry.get("board", "").upper()
            year = carry.get("year", "")
            post, bps = carry.get("post", ""), carry.get("bps", "")
            q = pick(row, "Question", "Question Text", "Q")
            opts = [pick(row, "Option A", "A"), pick(row, "Option B", "B"),
                    pick(row, "Option C", "C"), pick(row, "Option D", "D")]
            a = answer(pick(row, "Answer", "Correct Answer", "Correct", "Key"), opts)
            subj_raw = pick(row, "Subject")
            subj = ALIASES.get(re.sub(r"[^a-z]", "", subj_raw.lower()), "")
            problems = []
            if board not in BOARDS:
                problems.append(f'board "{board}" is not one of {", ".join(BOARDS)}')
            if not re.fullmatch(r"(19|20)\d\d", str(year).split(".")[0]):
                problems.append(f'year "{year}" is not a year')
            if not post:
                problems.append("no position")
            if not level(bps):
                problems.append(f'grade "{bps}" has no BPS number')
            if not subj:
                problems.append(f'subject "{subj_raw}" is not one of {", ".join(SUBJECTS.values())}')
            if not q:
                problems.append("no question")
            if not all(opts):
                problems.append("missing option")
            if a < 0:
                problems.append("no correct answer")
            if problems:
                errors.append(f"{where}: " + "; ".join(problems))
                continue
            year = int(str(year).split(".")[0])
            pid = slug(board, year, post, bps)
            p = papers.setdefault(pid, {"id": pid, "board": board, "year": year, "post": post,
                                        "bps": bps, "qs": []})
            key = (pid, q, tuple(opts))
            if key in ids:
                errors.append(f"{where}: the same question is already in {pid}")
                continue
            ids.add(key)
            item = {"s": subj, "q": q, "o": opts, "a": a}
            e, d = pick(row, "Explanation", "Why"), level(pick(row, "Difficulty", "Level"))
            if e:
                item["e"] = e
            if d:
                item["d"] = d
            p["qs"].append(item)

    if errors:
        print(f"{len(errors)} problem(s) — nothing written:")
        for e in errors:
            print("  " + e)
        sys.exit(1)

    out = sorted(papers.values(), key=lambda p: (p["board"], -p["year"], p["post"]))
    OUT.write_text("/* Generated by branding/build_past_papers.py — edit the spreadsheets, not this file. */\n"
                   "window.PAST_PAPERS = " + json.dumps({"papers": out}, ensure_ascii=False) + ";\n",
                   encoding="utf-8")
    print(f"Wrote {OUT.name}: {len(out)} paper(s), {sum(len(p['qs']) for p in out)} question(s)")
    for p in out:
        counts = {}
        for q in p["qs"]:
            counts[SUBJECTS[q["s"]]] = counts.get(SUBJECTS[q["s"]], 0) + 1
        print(f"  {p['board']} {p['year']} · {p['post']} · {p['bps']} — " +
              ", ".join(f"{k} {v}" for k, v in counts.items()))


def write_template():
    """A one-sheet xlsx with just the header row, built by hand so no library is needed."""
    def col(i):
        s = ""
        i += 1
        while i:
            i, r = divmod(i - 1, 26)
            s = chr(65 + r) + s
        return s
    cells = "".join(f'<c r="{col(i)}1" t="inlineStr"><is><t>{h}</t></is></c>' for i, h in enumerate(COLUMNS))
    parts = {
        "[Content_Types].xml": '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>',
        "_rels/.rels": '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        "xl/workbook.xml": '<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Past paper" sheetId="1" r:id="rId1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels": '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
        "xl/worksheets/sheet1.xml": f'<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1">{cells}</row></sheetData></worksheet>',
    }
    SRC.mkdir(exist_ok=True)
    dest = SRC / "TEMPLATE.xlsx"
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for name, xml in parts.items():
            z.writestr(name, xml)
    print(f"Wrote {dest}")


if __name__ == "__main__":
    if "--template" in sys.argv:
        write_template()
    else:
        SRC.mkdir(exist_ok=True)
        build()
