"""Builds the online feed for News & Opinions and Current Affairs into branding/feed-out/.

Usage: build_feed.py [--keep-days 30] [--news-hours 24]

Upload everything inside feed-out/ to your content address (for example a GitHub Pages
repository). The app reads index.json from there whenever it is online, so nothing
has to be rebuilt or reinstalled for new news to appear.

One item per .md file, in the folder for its kind:
  feed/news/2026-11-03-summary.md         News & Opinions
  feed/ca-daily/2026-11-03.md             Current Affairs · Daily     (online only)
  feed/ca-weekly/2026-w45.md              Current Affairs · Weekly    (online only)
  feed/ca-monthly/2026-11.md              Current Affairs · Monthly   (saved on the phone)
  feed/ca-yearly/2026.md                  Current Affairs · Yearly    (saved on the phone)
  feed/ca-notes/budget-2026.md            Current Affairs · Notes     (your own reading cards, saved on the phone)
Files whose name starts with "_" are skipped (see feed/_EXAMPLE.md).

Each file starts with a short header, then the text, written as in branding/learn/:
  ---
  title: CM incensed at Chaudhry Salik's claims of corruption in Punjab
  date: 2026-11-03
  source: Dawn Editorial              (shown under the title)
  logo: logos/dawn.png                (optional, a picture in feed/; "examprep" uses the app's own logo)
  image: pictures/cm.jpg              (optional, the picture on the card; a web address works too)
  pin: yes                            (optional, keeps it at the very top — use it for the News Summary)
  time: 09:00                         (optional, ca-daily: when it was posted; the MCQs count as
                                       "today's" for 24 hours from then — midnight if left out)
  mcqs: 2026-11-03.xlsx               (optional, any current-affairs kind: MCQs that go into Current Affairs)
  ---
Daily and weekly MCQs are downloaded to the phone straight away and kept there. In the app they sit
under "Today's MCQs" for 24 hours, then "This week's MCQs"; when the week ends they move to a page
for their month, named like "Nov 2026", and on the 1st of each month the month before is complete.
Monthly and yearly files keep their MCQs under their own title.
The MCQ sheet uses the same columns as the subject template:
  Question, Option A, Option B, Option C, Option D, Answer, Explanation, Difficulty, Topic
An MCQ sheet may have an Id column: the app then keeps that id, so answers given to a daily
MCQ still count after ingest.py has moved it into its month's file.
News is a 24-hour page: with --news-hours 24 an item leaves index.json that long after its
date and time (Pakistan time), and the app hides it at the same moment even between builds.
Daily and weekly items older than --keep-days drop out of index.json.
Nothing is written if any file has a problem. Only the standard library is used."""
import datetime
import hashlib
import json
import pathlib
import re
import shutil
import sys

from build_learn import IMG_EXT, parse_body, read_md, slug
from build_past_papers import answer, level, pick, read_rows

ROOT = pathlib.Path(__file__).resolve().parent
SRC = ROOT / "feed"
OUT = ROOT / "feed-out"
KINDS = {"news": "news", "ca-daily": "daily", "ca-weekly": "weekly", "ca-monthly": "monthly", "ca-yearly": "yearly",
         "ca-notes": "notes"}
KEPT = ("monthly", "yearly", "notes")   # saved on the phone, never dropped by --keep-days
PKT = datetime.timezone(datetime.timedelta(hours=5))


def picture_into(out_img, md_path, prefix):
    def picture(src):
        if re.match(r"https?://", src) or src.lower() == "examprep":
            return src.lower() if src.lower() == "examprep" else src
        f = (md_path.parent / src).resolve()
        if not f.is_file():
            f = (SRC / src).resolve()
        if not f.is_file():
            raise ValueError(f'picture "{src}" not found')
        if f.suffix.lower() not in IMG_EXT:
            raise ValueError(f'picture "{src}" must be .jpg, .png, .webp or .gif')
        out_img.mkdir(parents=True, exist_ok=True)
        name = slug(prefix, f.stem) + f.suffix.lower()
        shutil.copyfile(f, out_img / name)
        return "img/" + name
    return picture


def mcqs_from(path, month):
    rows, out = read_rows(path), []
    for n, r in enumerate(rows, start=2):
        q = pick(r, "Question", "Statement")
        opts = [pick(r, f"Option {c}", c) for c in "ABCD"]
        if not q:
            continue
        a = answer(pick(r, "Answer", "Correct"), opts)
        if a < 0 or not all(opts):
            raise ValueError(f"{path.name} row {n}: needs four options and an answer A-D")
        out.append({"q": q, "o": opts, "a": a, "e": pick(r, "Explanation"),
                    "d": level(pick(r, "Difficulty", "Level")), "t": pick(r, "Topic") or month})
        if pick(r, "Id"):
            out[-1]["i"] = pick(r, "Id")
    return out


def main():
    keep = 30
    if "--keep-days" in sys.argv:
        keep = int(sys.argv[sys.argv.index("--keep-days") + 1])
    news_hours = int(sys.argv[sys.argv.index("--news-hours") + 1]) if "--news-hours" in sys.argv else 0
    now = datetime.datetime.now(PKT).replace(tzinfo=None)
    cutoff = (now.date() - datetime.timedelta(days=keep)).isoformat()
    SRC.mkdir(exist_ok=True)
    for k in KINDS:
        (SRC / k).mkdir(exist_ok=True)
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "items").mkdir(parents=True)
    index, errors = [], []
    for folder, kind in KINDS.items():
        for f in sorted((SRC / folder).glob("*.md")):
            if f.name.startswith("_"):
                continue
            try:
                meta, body = read_md(f)
                date = meta.get("date", "")
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
                    raise ValueError("header needs a date like 2026-11-03")
                if kind not in KEPT and date < cutoff:
                    continue
                if kind == "news" and news_hours:
                    posted = datetime.datetime.fromisoformat(date + "T" + (meta.get("time") or "00:00").zfill(5))
                    if now - posted >= datetime.timedelta(hours=news_hours):
                        continue
                iid = slug(kind, f.stem)
                pic = picture_into(OUT / "img", f, iid)
                blocks = parse_body(body, pic)
                item = {"blocks": blocks}
                if kind != "news" and meta.get("mcqs"):
                    sheet = f.parent / meta["mcqs"]
                    if not sheet.is_file():
                        raise ValueError(f'mcqs file "{meta["mcqs"]}" not found')
                    item["mcqs"] = mcqs_from(sheet, meta["title"])
                text = json.dumps(item, ensure_ascii=False)
                (OUT / "items" / f"{iid}.json").write_text(text, encoding="utf-8")
                row = {"id": iid, "kind": kind, "date": date, "title": meta["title"],
                       "v": hashlib.sha1(text.encode()).hexdigest()[:10]}
                if meta.get("time"):
                    if not re.fullmatch(r"\d{1,2}:\d{2}", meta["time"]):
                        raise ValueError("time must look like 09:00")
                    row["time"] = meta["time"]
                for k in ("source", "logo", "image"):
                    if meta.get(k):
                        row["img" if k == "image" else k] = pic(meta[k]) if k != "source" else meta[k]
                if meta.get("pin", "").lower() in ("yes", "true", "1"):
                    row["pin"] = 1
                if item.get("mcqs"):
                    row["mcqs"] = len(item["mcqs"])
                index.append(row)
            except ValueError as e:
                errors.append(f"{folder}/{f.name}: {e}")
    if errors:
        shutil.rmtree(OUT)
        print(f"{len(errors)} problem(s) — nothing written:")
        for e in errors:
            print("  " + e)
        sys.exit(1)
    index.sort(key=lambda r: r["date"], reverse=True)
    # settings.json next to this script travels with the index: the app's plan switch and
    # the length of the free PRO period, changed without updating the app
    settings = json.loads((ROOT / "settings.json").read_text(encoding="utf-8")) if (ROOT / "settings.json").exists() else {}
    (OUT / "index.json").write_text(json.dumps(
        {"updated": datetime.datetime.now().isoformat(timespec="minutes"), "settings": settings, "items": index},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Wrote feed-out/: {len(index)} item(s) — upload the whole folder")
    for r in index:
        print(f"  {r['kind']:8} {r['date']}  {r['title']}" + ("  [pinned]" if r.get("pin") else ""))


if __name__ == "__main__":
    main()
