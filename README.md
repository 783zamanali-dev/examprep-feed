# ExamPrep feed

This folder is a ready-made GitHub repository. It publishes the app's **News & Opinions** and
**Current Affairs** every day without anyone touching it:

```
04:00  n8n reads the newspapers' RSS feeds
       → Claude chooses the 8–15 pieces worth reading and scores them
       → Claude writes a card for each, the front-page summary and 15–30 MCQs
       → n8n saves one file, inbox/<date>-<time>.json, into this repository
       GitHub Actions then runs ingest.py and build_feed.py and publishes the result
       → every phone that is online shows it within minutes
```

Nothing else needs a server. The app does the rest by the clock:

| What | Where it shows | For how long |
|---|---|---|
| News cards and the summary | News & Opinions | 24 hours, then gone. A post the user saved stays on that phone until they remove it |
| The day's current affairs file | Current Affairs › Daily | 24 hours, then it moves to Weekly, and after the week to Monthly |
| The day's MCQs | Today's MCQs | 24 hours → This week's MCQs → the month's page (e.g. "Nov 2026") |
| A finished month | Current Affairs › Monthly | Built on the 1st from that month's daily MCQs; kept on the phone |
| Yearly files and Notes | Current Affairs › Yearly / Notes | You add these yourself (below); kept on the phone |

## Set it up once

### 1. Put this folder on GitHub
1. Create a free account at github.com and a new **public** repository named `examprep-feed`.
2. Upload everything in this folder to it (drag the files into "uploading an existing file",
   or use GitHub Desktop). The `.github` folder must go up too.
3. In the repository: **Settings › Pages › Build and deployment › Source: GitHub Actions**.
4. **Actions** tab → "Publish feed" → **Run workflow**. When it is green, your feed address is
   `https://YOUR_GITHUB_USERNAME.github.io/examprep-feed/`. Opening
   `…/examprep-feed/index.json` in a browser should show a small file.

### 2. Tell the app the address
In `ExamPrepApp/app/src/main/assets/index.html` find `const FEED_URL = '';` and put the address
between the quotes, ending with `/`. Build the app again. (This is the only app change needed.)

### 3. Import the n8n workflow
1. In n8n: **Workflows › Import from file** → `n8n/examprep-daily-news.json`.
2. Open the **Config** node and change `YOUR_GITHUB_USERNAME`. Sources, the model, and how many
   cards and MCQs you want are all in that one node.
3. Credentials (n8n keeps them; they are not in the file):
   - On both **Claude** nodes choose or create an **Anthropic** credential with your API key.
   - On **Save to GitHub** choose or create a **GitHub API** credential. Use a fine-grained
     personal access token limited to the `examprep-feed` repository with **Contents: Read and
     write** — nothing more.
4. Press **Test workflow** once. The last node should show a new file in `inbox/`. A minute or
   two later the Actions tab is green and the app shows the day.
5. Switch the workflow to **Active**. It runs at 04:00 Pakistan time every day; change the time
   in the first node.

Cost: with `claude-opus-5-5` a day is roughly 45,000 tokens in and 9,000 out, about 35 US cents.
`claude-sonnet-5-5` is about half that and `claude-haiku-5-5` about one cent. If a request is
declined by the model's safety filters the workflow lets the API fall back to another Claude
model on its own (the `fallbacks` line in the two request nodes).

## What you add by hand

Write a `.md` file as `feed/_EXAMPLE.md` shows, put it in the right folder, and commit it:

- `feed/ca-yearly/2026.md` (+ its MCQ sheet) — the year's current affairs
- `feed/ca-notes/anything.md` — a reading card under Current Affairs › **Notes**
- `feed/ca-weekly/…` or `feed/news/…` — anything extra you want to post yourself

## The rules the pipeline keeps

- **Must read gets a card, skim goes in the summary.** Only pieces scored 8–10 get their own
  card. Pieces scored 5–7 are told inside the pinned **News Summary** card, under "Worth a
  skim", after the National and International headlines.
- **Full text is a switch per paper.** In the n8n **Config** node, `fullText` lists each paper
  as `false`. While it is `false`, a must-read card is ExamPrep's own summary with a link. Set a
  paper to `true` from the day your signed agreement with it starts: its must-read cards then
  show the article word for word, followed by our key facts, vocabulary and the link. Skim
  pieces stay in the summary card either way.
- **Own words only (while the switch is off).** A card is ExamPrep's own summary, key facts and vocabulary, with a
  "Read the full article at …" link. The article's text is sent to Claude to be analysed and is
  never stored or shown. No newspaper photographs are used.
- **Headline, link, author and source come from the feed**, not from the model, so they cannot
  be invented.
- **Logos.** A card shows the source's name as text. It shows a logo only if you put one in
  `feed/logos/` (`dawn.png`, `the-express-tribune.png`, `foreign-affairs.png`). Do that only
  with the paper's written permission.
- **Foreign Affairs** publishes only a headline and one line in its feed, so its cards are
  short, say "From the published summary", and produce no MCQs.
- A broken MCQ (not four different options, no answer) is left out and named in the Actions log.

MCQs written by a model can still be wrong. The prompts allow only facts found in the article
text, but read a few each morning for the first weeks before you trust the run.

## Changing things

| To change | Edit |
|---|---|
| Sources, model, number of cards or MCQs | the **Config** node in n8n (or `n8n/code/1-config.js`) |
| How stories are chosen | the prompt in `n8n/code/2-candidates.js` |
| How cards, summary and MCQs are written | the prompt in `n8n/code/3-write-request.js` |
| How a card looks in the app | `ingest.py` |

After editing a file in `n8n/code/`, run `python n8n/build_workflow.py` and import the new
`examprep-daily-news.json` again.
