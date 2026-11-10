"""Builds app/src/main/assets/learn.js from the articles in branding/learn/.

Usage: build_learn.py

One article per .md file, in a folder named after the board it belongs to:
  learn/FIA/constitution-part-1.md     shows under FIA
  learn/ALL/how-to-revise.md           shows under every board
  learn/mathematics/fractions.md       shows in the Learn block inside Mathematics
Subject folders: islamic-studies, pakistan-affairs, mathematics, general-knowledge,
everyday-science, english, urdu, logical-reasoning, computer, current-affairs. Users can read and
highlight these but cannot change or delete them; they arrive with app updates.
Files whose name starts with "_" are skipped (see learn/_EXAMPLE.md).

Each file starts with a short header, then the text:
  ---
  title: The 1973 Constitution
  series: Constitution of Pakistan      (optional — articles in a series get "Next part")
  part: 1                               (optional, orders the series)
  tags: constitution, law               (optional — used for "Read next")
  ---
  ## A section heading                  (becomes an entry in Contents)
  A paragraph. Blank lines separate paragraphs. **Bold** for key points only.
  - a bullet point
  > a key point, shown in a box
  ![What the picture shows](picture.jpg)   a picture kept next to the .md file (or a web address)
  | Year | Amendment |                      a table: the first row is the heading row
  | 1985 | 8th       |
  [Dawn](https://www.dawn.com)            a link
  A fact that needs a source.[^1]         a footnote; write the source on its own line at the end:
  [^1]: Constitution of Pakistan, Article 1
A Word file (.docx) in a subject or board folder works too, with no header: its first line is
the title (ALL CAPS becomes Title Case; a leading number in the file name, "1-full.docx", sets the order), the line under it is skipped as a subtitle, Heading 1 /
Heading 2 become sections (a trailing count like "(14)" is dropped), and tables become bullet
points (a first row that is not a "•" bullet is taken as the table's caption and skipped).
An article whose title is in Urdu script is tagged lang "ur" (a .md header can say "lang: ur").
In Islamic Studies the English / اردو switch then shows only the articles in that language.
Pictures are copied into assets/learn-img/. Nothing is written if any file has a problem. Only the standard library is used."""
import json
import pathlib
import re
import shutil
import sys
import zipfile
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent
SRC = ROOT / "learn"
ASSETS = ROOT.parent / "app" / "src" / "main" / "assets"
OUT = ASSETS / "learn.js"
IMG_OUT = ASSETS / "learn-img"
IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
BOARDS = ["FIA", "MOD", "FPSC", "KPSC", "SPSC", "PPSC", "BPSC", "AJK", "GB", "NTS", "PMS", "PCS",
          "PTS", "OTS", "ALL"]
# folder name -> the built-in subject's key in the app (index.html, BASE_SUBJECTS)
SUBJECTS = {"islamic-studies": "islamiyat", "islamiyat": "islamiyat", "pakistan-affairs": "pakistan_affairs",
            "mathematics": "maths", "maths": "maths", "general-knowledge": "general_knowledge",
            "everyday-science": "everyday_science", "english": "english", "urdu": "urdu",
            "logical-reasoning": "psychological", "current-affairs": "current_affairs",
            "computer": "computer"}


def slug(*parts):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", " ".join(map(str, parts)).lower())).strip("-")


def read_md(path):
    """The header as a dict, and the text under it."""
    text = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    m = re.match(r"---\n(.*?)\n---\n(.*)", text, re.S)
    if not m:
        raise ValueError("starts without a --- header block")
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip().lower()] = v.strip()
    if not meta.get("title"):
        raise ValueError("header has no title")
    return meta, m.group(2)


W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
URDU = re.compile(r"[؀-ۿ]")


def docx_text(el):
    """A paragraph or cell's text, with bold runs as **bold**."""
    out = []
    for r in el.iter(W + "r"):
        t = "".join(x.text or "" for x in r.iter(W + "t"))
        b = r.find(W + "rPr")
        b = b.find(W + "b") if b is not None else None
        bold = b is not None and b.get(W + "val") not in ("0", "false")
        if bold and t.strip():               # keep the spaces outside the ** marks
            lead, core, trail = re.match(r"(\s*)(.*?)(\s*)$", t, re.S).groups()
            t = f"{lead}**{core}**{trail}"
        out.append(t)
    return re.sub(r"\*\*(\s*)\*\*", r"\1", "".join(out)).strip()   # join neighbouring bold runs


BULLET = re.compile(r"\s*(?:•|★|- )")
SMALL = {"OF", "TO", "IN", "ON", "AT", "BY", "AN", "OR", "A"}


def caps_title(t):
    """ALL CAPS -> Title Case, keeping short acronyms: "GK STUDY NOTES" -> "GK Study Notes"."""
    cap = lambda w: "-".join(p.capitalize() for p in w.split("-"))
    return " ".join(w if len(re.sub(r"\W", "", w)) <= 2 and w not in SMALL else cap(w) if i == 0 or w not in SMALL
                    else w.lower() for i, w in enumerate(t.split()))


def read_docx(path):
    """A Word file -> (header dict, Markdown text), the same shape read_md gives."""
    body = ET.fromstring(zipfile.ZipFile(path).read("word/document.xml")).find(W + "body")
    title, lines, plain = "", [], 0
    for el in body:
        tag = el.tag.replace(W, "")
        if tag == "p":
            ps = el.find(W + "pPr")
            st = ps.find(W + "pStyle") if ps is not None else None
            st = (st.get(W + "val") or "").lower() if st is not None else ""
            text = docx_text(el)
            bare = text.replace("**", "").strip()
            if not bare:
                continue
            if st.startswith("heading"):
                lines += ["", "## " + re.sub(r"\s*\(\d+\)$", "", bare), ""]
            elif not title:
                title = caps_title(bare) if bare.isupper() else bare
            elif plain == 0 and not lines:
                plain = 1                       # the subtitle under the title
            elif ps is not None and ps.find(W + "numPr") is not None:
                lines.append("- " + text)      # a numbered or bulleted Word list
            else:
                lines += ["", text, ""]
        elif tag == "tbl":
            for i, row in enumerate(el.iter(W + "tr")):
                tcs = list(row.iter(W + "tc"))
                if len(tcs) > 1:
                    cells = [" ".join(filter(None, (docx_text(p) for p in c.iter(W + "p")))) for c in tcs]
                    if any(c.replace("**", "").strip() for c in cells):
                        lines.append("| " + " | ".join(c.replace("|", "/") for c in cells) + " |")
                    continue
                # one column: every line in the cell is its own fact
                facts = [t for t in (docx_text(p) for p in tcs[0].iter(W + "p")) if t.replace("**", "").strip()]
                if i == 0 and facts and not BULLET.match(facts[0].replace("**", "")):
                    facts = facts[1:]              # the caption row repeats the section heading
                for t in facts:
                    lines.append("- " + re.sub(r"^(\*\*)?\s*(?:•|- )\s*", lambda m: m.group(1) or "", t))
            lines.append("")
    if not title:
        raise ValueError("has no title line")
    return {"title": title}, "\n".join(lines)


def parse_body(body, picture):
    """Text -> the app's blocks. picture(name) copies a local picture and returns its address.
    Shared with build_feed.py, so news and reading cards are written the same way."""
    blocks, para, table, notes = [], [], [], {}

    def flush():
        if para:
            blocks.append({"t": "p", "x": " ".join(para)})
            para.clear()
        if table:
            rows = [[c.strip() for c in r.strip().strip("|").split("|")] for r in table
                    if not re.fullmatch(r"\|?[\s:|-]+\|?", r.strip())]      # drop the |---|---| line
            blocks.append({"t": "table", "rows": rows})
            table.clear()

    for raw in body.splitlines():
        line = raw.strip()
        fn = re.match(r"\[\^(\w+)\]:\s*(.+)", line)
        img = re.fullmatch(r"!\[(.*?)\]\((\S+?)\)", line)
        if not line:
            flush()
        elif fn:
            flush()
            notes[fn.group(1)] = fn.group(2)
        elif line.startswith("|"):
            if para:
                flush()
            table.append(line)
        elif img:
            flush()
            blocks.append({"t": "img", "src": picture(img.group(2)), **({"cap": img.group(1)} if img.group(1) else {})})
        elif line.startswith("# "):
            flush()                      # a repeated title line; the header already has it
        elif line.startswith("## ") or line.startswith("### "):
            flush()
            blocks.append({"t": "h", "x": line.lstrip("#").strip()})
        elif re.match(r"[-*•] ", line):
            flush()
            blocks.append({"t": "li", "x": line[2:].strip()})
        elif line.startswith(">"):
            flush()
            blocks.append({"t": "quote", "x": line.lstrip("> ").strip()})
        else:
            if table:
                flush()
            para.append(line)
    flush()
    # footnotes are numbered in the order they are first used
    order = []
    for b in blocks:
        for k in re.findall(r"\[\^(\w+)\]", b.get("x", "")):
            if k in notes and k not in order:
                order.append(k)
    if order:
        num = {k: i + 1 for i, k in enumerate(order)}
        for b in blocks:
            if "x" in b:
                b["x"] = re.sub(r"\[\^(\w+)\]", lambda m: f"[^{num[m.group(1)]}]" if m.group(1) in num else "", b["x"])
        blocks.append({"t": "h", "x": "References"})
        blocks += [{"t": "ref", "n": num[k], "x": f"{num[k]}. {notes[k]}"} for k in order]
    return blocks


def local_picture(md_path, out_dir, prefix):
    """Copies a picture named in an article next to the app and returns where the app finds it."""
    def picture(src):
        if re.match(r"https?://", src):
            return src
        f = (md_path.parent / src).resolve()
        if not f.is_file():
            raise ValueError(f'picture "{src}" not found next to {md_path.name}')
        if f.suffix.lower() not in IMG_EXT:
            raise ValueError(f'picture "{src}" must be .jpg, .png, .webp or .gif')
        out_dir.mkdir(parents=True, exist_ok=True)
        name = slug(prefix, f.stem) + f.suffix.lower()
        shutil.copyfile(f, out_dir / name)
        return out_dir.name + "/" + name
    return picture


def parse(path, board):
    meta, body = read_docx(path) if path.suffix.lower() == ".docx" else read_md(path)
    blocks = parse_body(body, local_picture(path, IMG_OUT, board))
    if not blocks:
        raise ValueError("has no text after the header")
    art = {"id": slug(board, path.stem), "board": board, "title": meta["title"], "blocks": blocks}
    if meta.get("series"):
        art["series"] = meta["series"]
    if meta.get("part"):
        if not meta["part"].isdigit():
            raise ValueError(f'part "{meta["part"]}" is not a number')
        art["part"] = int(meta["part"])
    lead = re.match(r"(\d+)[-_ ]", path.name)
    if "part" not in art and lead:            # "1-english-full.docx" lists before "2-..."
        art["part"] = int(lead.group(1))
    lang = meta.get("lang", "").lower() or ("ur" if URDU.search(meta["title"]) else "")
    if lang and lang != "en":
        art["lang"] = lang
    if meta.get("tags"):
        art["tags"] = [t.strip().lower() for t in meta["tags"].split(",") if t.strip()]
    return art


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    SRC.mkdir(exist_ok=True)
    arts, errors = [], []
    for folder in sorted(p for p in SRC.iterdir() if p.is_dir()):
        board = SUBJECTS.get(folder.name.lower()) or folder.name.upper()
        if board not in BOARDS and board not in SUBJECTS.values():
            errors.append(f'{folder.name}/: folder name must be a subject ({", ".join(sorted(set(SUBJECTS) - {"maths", "islamiyat"}))})'
                          f' or a board ({", ".join(BOARDS)})')
            continue
        for f in sorted(p for p in folder.iterdir() if p.suffix.lower() in (".md", ".docx")):
            if f.name.startswith(("_", "~$")):
                continue
            try:
                arts.append(parse(f, board))
            except ValueError as e:
                errors.append(f"{folder.name}/{f.name}: {e}")
    if errors:
        print(f"{len(errors)} problem(s) — nothing written:")
        for e in errors:
            print("  " + e)
        sys.exit(1)
    OUT.write_text("/* Generated by branding/build_learn.py — edit the articles in branding/learn/, not this file. */\n"
                   "window.LEARN = " + json.dumps({"articles": arts}, ensure_ascii=False) + ";\n",
                   encoding="utf-8")
    print(f"Wrote {OUT.name}: {len(arts)} article(s)")
    for a in arts:
        words = sum(len(b.get("x", "").split()) for b in a["blocks"])
        print(f"  {a['board']:17} {a['title']}  ({words} words, ~{max(1, round(words / 180))} min)")


if __name__ == "__main__":
    main()
