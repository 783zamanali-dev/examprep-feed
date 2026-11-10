"""Turns the day packs n8n drops into inbox/ into feed files, and keeps the feed tidy.

  python ingest.py          then          python build_feed.py --news-hours 24

The publish workflow (.github/workflows/publish.yml) runs both on every push and once an hour.

A day pack is one JSON file, inbox/2026-11-10-0610.json, written by the n8n workflow:
  {"date": "2026-11-10", "time": "06:10",
   "summary": {"national": [{"headline", "line", "source", "url"}], "international": [...]},
   "cards":   [{"source", "url", "title", "author", "section", "tags": [], "score", "priority",
                "why", "summary", "key_facts": [], "vocab": [{"word", "meaning"}]}],
   "mcqs":    [{"q", "options": [4], "answer": "A".."D", "explanation", "difficulty", "topic"}]}
From it this writes
  feed/news/<date>-00-summary.md        the ExamPrep summary, pinned to the top of News & Opinions
  feed/news/<date>-NN-<title>.md        one card per MUST-READ article: our own summary, key facts,
                                        vocabulary and a link to the original. Never the article's own
                                        text. Pieces marked "skim" are told inside the summary card.
  feed/ca-daily/<date>.md + .csv        the day's key facts and its MCQs
A pack is moved to inbox/done/ once it is in, so a rerun never doubles anything.

Housekeeping, every run:
  - news files more than 3 days old are deleted (the app shows news for 24 hours only)
  - once a month is over, its daily MCQs are gathered into feed/ca-monthly/<YYYY-MM>.md + .csv
    and the daily files move to archive/. Each MCQ keeps its id, so answers already given on
    a phone still count, and a phone installed later gets the whole month in one download.
A logo is used only if a picture for that source is in feed/logos/ (dawn.png for "Dawn",
express-tribune.png, foreign-affairs.png ...). Without one the card shows the source's name.
Put a newspaper's logo there only with its permission.
Only the standard library is used."""
import calendar
import csv
import datetime
import json
import pathlib
import re
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent
FEED, INBOX, ARCHIVE = ROOT / "feed", ROOT / "inbox", ROOT / "archive"
PKT = datetime.timezone(datetime.timedelta(hours=5))
MCQ_HEAD = ["Id", "Question", "Option A", "Option B", "Option C", "Option D", "Answer", "Explanation", "Difficulty", "Topic"]
LEVELS = {"basic": "Basic", "easy": "Easy", "medium": "Medium", "hard": "Hard"}
PRIORITY = {"must_read": "Must read", "skim": "Skim"}


def slug(*parts):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", " ".join(map(str, parts)).lower())).strip("-")


def one_line(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


def md_safe(s):
    """Text that cannot be mistaken for a heading, bullet, table or picture when it starts a line."""
    s = one_line(s)
    return re.sub(r"^([#>|\-*!\[])", r"\\\1", s)


def logo_for(source):
    for ext in (".png", ".webp", ".jpg", ".jpeg"):
        if (FEED / "logos" / (slug(source) + ext)).is_file():
            return "logos/" + slug(source) + ext
    return ""


def header(**fields):
    return "---\n" + "".join(f"{k}: {one_line(v)}\n" for k, v in fields.items() if v) + "---\n"


def long_date(d):
    return f"{d.day} {calendar.month_name[d.month]} {d.year}"


def clean_mcqs(raw, problems, where):
    out, seen = [], set()
    for n, m in enumerate(raw or [], start=1):
        q = one_line(m.get("q"))
        opts = [one_line(o) for o in (m.get("options") or [])]
        ans = one_line(m.get("answer")).upper()[:1]
        if not q or len(opts) != 4 or not all(opts) or len({o.lower() for o in opts}) != 4 or ans not in "ABCD" or not ans:
            problems.append(f"{where}: MCQ {n} left out (needs a question, four different options and an answer A-D)")
            continue
        if q.lower() in seen:
            continue
        seen.add(q.lower())
        out.append({"q": q, "o": opts, "a": ans, "e": one_line(m.get("explanation")),
                    "d": LEVELS.get(one_line(m.get("difficulty")).lower(), "Medium"), "t": one_line(m.get("topic"))})
    return out


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, quoting=csv.QUOTE_ALL)
        w.writerow(MCQ_HEAD)
        w.writerows(rows)


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def ingest_pack(path, problems):
    pack = json.loads(path.read_text(encoding="utf-8-sig"))
    date = one_line(pack.get("date"))
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        raise ValueError("no date like 2026-11-10")
    time = one_line(pack.get("time")) if re.fullmatch(r"\d{1,2}:\d{2}", one_line(pack.get("time"))) else "06:00"
    day = datetime.date.fromisoformat(date)

    # 1. the summary that sits on top of News & Opinions
    summary, lines = pack.get("summary") or {}, []
    for title, key in (("National", "national"), ("International", "international")):
        rows = [r for r in summary.get(key) or [] if one_line(r.get("headline"))]
        if rows:
            lines += ["", f"## {title}", ""]
            lines += [f"- **{md_safe(r['headline'])}** — {one_line(r.get('line'))}"
                      + (f" ([{one_line(r.get('source')) or 'source'}]({one_line(r['url'])}))" if one_line(r.get("url")) else "")
                      for r in rows]
    # Only the must-read pieces get a card of their own. Everything marked "skim" is told
    # inside the summary card instead, so the News page stays short.
    every = [c for c in pack.get("cards") or [] if one_line(c.get("title")) and one_line(c.get("summary"))]
    every.sort(key=lambda c: -(c.get("score") or 0))
    cards = [c for c in every if one_line(c.get("priority")) != "skim"]
    skim = [c for c in every if one_line(c.get("priority")) == "skim"]
    facts_by_tag = {}
    if skim:
        lines += ["", "## Worth a skim", ""]
        for c in skim:
            src = one_line(c.get("source")) or "source"
            lines += [f"**{md_safe(c['title'])}** ({' · '.join(x for x in (src, one_line(c.get('author'))) if x)})", "",
                      md_safe(one_line(c["summary"])), ""]
            facts = [one_line(f) for f in c.get("key_facts") or [] if one_line(f)]
            lines += [f"- ★ {f}" for f in facts] + ([""] if facts else [])
            facts_by_tag.setdefault(one_line((c.get("tags") or ["Current Affairs"])[0]), []).extend(facts)
            if one_line(c.get("url")):
                lines += [f"[Read it at {src}]({one_line(c['url'])})", ""]
    if lines:
        (FEED / "news" / f"{date}-00-summary.md").write_text(
            header(title=f"News Summary · {long_date(day)}", date=date, time=time, source="ExamPrep Summary", logo="examprep", pin="yes")
            + "The day in one card: the headlines that matter for the exam, and the pieces worth only a skim. "
              "The must-read pieces have their own cards below.\n"
            + "\n".join(lines) + "\n", encoding="utf-8")

    # 2. one card per must-read article: our own words, and a link to the original
    for n, c in enumerate(cards, start=1):
        source = one_line(c.get("source")) or "Source"
        body = []
        if one_line(c.get("why")):
            body += [f"> Why it matters: {one_line(c['why'])}", ""]
        text = [md_safe(p) for p in c.get("text") or [] if one_line(p)]
        # a paper whose full-text switch is on in n8n: its article, paragraph by paragraph.
        # Otherwise our own summary.
        body += text or [md_safe(p) for p in str(c["summary"]).split("\n") if p.strip()]
        body = [x for p in body for x in (p, "")]
        facts = [one_line(f) for f in c.get("key_facts") or [] if one_line(f)]
        if facts:
            body += ["## Key facts", ""] + [f"- ★ {f}" for f in facts] + [""]
            tag = one_line((c.get("tags") or ["Current Affairs"])[0])
            facts_by_tag.setdefault(tag, []).extend(facts)
        vocab = [v for v in c.get("vocab") or [] if one_line(v.get("word")) and one_line(v.get("meaning"))]
        if vocab:
            body += ["## Vocabulary", ""] + [f"- **{one_line(v['word'])}** — {one_line(v['meaning'])}" for v in vocab] + [""]
        if one_line(c.get("url")):
            body += [f"[Read the full article at {source}]({one_line(c['url'])})", ""]
        tags = [one_line(t) for t in c.get("tags") or [] if one_line(t)]
        if tags:
            body += ["Syllabus: " + ", ".join(tags), ""]
        credit = " · ".join(x for x in (source, one_line(c.get("section")), one_line(c.get("author")),
                                        PRIORITY.get(one_line(c.get("priority")))) if x)
        (FEED / "news" / f"{date}-{n:02d}-{slug(c['title'])[:50]}.md").write_text(
            header(title=c["title"], date=date, time=time, source=credit, logo=logo_for(source)) + "\n".join(body),
            encoding="utf-8")

    # 3. the day's current affairs: key facts to read, MCQs to practise
    mcqs = clean_mcqs(pack.get("mcqs"), problems, path.name)
    if mcqs or facts_by_tag:
        body = [f"The facts and figures worth keeping from {long_date(day)}, and {len(mcqs)} MCQs made from them."]
        for tag, facts in facts_by_tag.items():
            body += ["", f"## {tag}", ""] + [f"- ★ {f}" for f in facts]
        if mcqs:
            write_csv(FEED / "ca-daily" / f"{date}.csv",
                      [["", m["q"], *m["o"], m["a"], m["e"], m["d"], m["t"]] for m in mcqs])
        (FEED / "ca-daily" / f"{date}.md").write_text(
            header(title=f"Current Affairs · {long_date(day)}", date=date, time=time, source="ExamPrep", logo="examprep",
                   mcqs=f"{date}.csv" if mcqs else "") + "\n".join(body) + "\n", encoding="utf-8")
    return len(cards), len(mcqs)


def tidy_news(today):
    gone = 0
    for f in (FEED / "news").glob("*.md"):
        m = re.match(r"(\d{4}-\d{2}-\d{2})-", f.name)
        if m and (today - datetime.date.fromisoformat(m.group(1))).days > 3:
            f.unlink()
            gone += 1
    return gone


def roll_months(today):
    """Every finished month's daily MCQs -> one monthly file. Returns the months rolled."""
    this = today.strftime("%Y-%m")
    by_month = {}
    for f in sorted((FEED / "ca-daily").glob("*.md")):
        m = re.fullmatch(r"(\d{4}-\d{2})-\d{2}", f.stem)
        if m and m.group(1) < this:
            by_month.setdefault(m.group(1), []).append(f)
    for month, files in by_month.items():
        y, mo = map(int, month.split("-"))
        topic = f"{calendar.month_abbr[mo]} {y}"                    # the page the app already keeps for the month
        sheet = FEED / "ca-monthly" / f"{month}.csv"
        rows = [[r.get(h, "") for h in MCQ_HEAD] for r in read_csv(sheet)] if sheet.exists() else []
        have = {r[0] for r in rows}
        days = []
        for f in files:
            days.append(int(f.stem[-2:]))
            src = f.with_suffix(".csv")
            if src.exists():
                for n, r in enumerate(read_csv(src)):
                    rid = r.get("Id") or f"ca_daily-{f.stem}_{n}"   # the id the app gave it as a daily MCQ
                    if rid not in have:
                        have.add(rid)
                        rows.append([rid] + [r.get(h, "") for h in MCQ_HEAD[1:-1]] + [topic])
            (ARCHIVE / "ca-daily").mkdir(parents=True, exist_ok=True)
            for x in (f, src):
                if x.exists():
                    shutil.move(str(x), str(ARCHIVE / "ca-daily" / x.name))
        if rows:
            write_csv(sheet, rows)
        last = datetime.date(y, mo, calendar.monthrange(y, mo)[1])
        (FEED / "ca-monthly" / f"{month}.md").write_text(
            header(title=f"Current Affairs · {calendar.month_name[mo]} {y}", date=last.isoformat(), source="ExamPrep",
                   logo="examprep", mcqs=f"{month}.csv" if rows else "")
            + f"Every current affairs MCQ of {calendar.month_name[mo]} {y} on one page: {len(rows)} questions from "
              f"{len(set(days))} day{'s' if len(set(days)) != 1 else ''}. Practise them under **{topic}** in Current Affairs.\n",
            encoding="utf-8")
    return sorted(by_month)


def main():
    for d in ("news", "ca-daily", "ca-weekly", "ca-monthly", "ca-yearly", "ca-notes", "logos"):
        (FEED / d).mkdir(parents=True, exist_ok=True)
    (INBOX / "done").mkdir(parents=True, exist_ok=True)
    today = datetime.datetime.now(PKT).date()
    problems, bad = [], 0
    for f in sorted(INBOX.glob("*.json")):
        try:
            cards, mcqs = ingest_pack(f, problems)
            print(f"{f.name}: {cards} news card(s), {mcqs} MCQ(s)")
            shutil.move(str(f), str(INBOX / "done" / f.name))
        except (ValueError, KeyError, TypeError, AttributeError) as e:      # one bad pack must not stop the feed
            bad += 1
            print(f"{f.name}: NOT ingested — {e}")
    for p in problems:
        print("  " + p)
    gone = tidy_news(today)
    rolled = roll_months(today)
    print(f"Tidy: {gone} old news file(s) removed" + (f"; month(s) completed: {', '.join(rolled)}" if rolled else ""))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
