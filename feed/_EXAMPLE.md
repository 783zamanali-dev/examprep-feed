---
title: Summary of all news
date: 2026-11-03
source: ExamPrep Summary
logo: examprep
pin: yes
---
How to write a news item (this file is skipped because its name starts with "_").

Copy it into news/ (or ca-daily/, ca-weekly/, ca-monthly/) under a new name, change the
header, write the text, then run:  python build_feed.py   and upload everything inside
feed-out/ to the content address. Phones that are online show it within minutes.

Header lines:
- title, date (YYYY-MM-DD) and source are shown on the card
- logo: a picture in feed/logos/ (for example logos/dawn.png), or "examprep" for the app's own logo
- image: the card picture, next to this file or a web address; leave it out on the summary to use the News Summary banner
- pin: yes keeps the item at the very top. Use it only for the day's News Summary
- mcqs: (any ca- folder) a spreadsheet next to the file with Question, Option A-D, Answer, Explanation, Difficulty, Topic.
  Daily and weekly MCQs go to the phone at once: "Today's MCQs" for 24 hours, then "This week's MCQs",
  then the month's page (e.g. "Nov 2026"). Put yearly files in ca-yearly/.
- time: (ca-daily, optional) when it was posted, e.g. 09:00 — the 24 hours count from then

## Writing the text
A paragraph. Blank lines separate paragraphs. **Bold** for key points only.

- a bullet point
> a key point, shown in a box

![What the picture shows](pictures/example.jpg)

| Year | Event |
|---|---|
| 1973 | Constitution passed |

Read the full editorial on [Dawn](https://www.dawn.com). A fact that needs a source.[^1]

[^1]: Dawn, 3 November 2026
