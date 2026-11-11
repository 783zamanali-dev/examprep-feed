// Reads every feed that came back, keeps the stories of the last day, and asks Claude which
// ones are worth a candidate's time. The article text is used only for this analysis: it is
// never saved or shown in the app.
const cfg = $('Config').first().json;
const feeds = $('Feeds').all();

const decode = s => String(s || '')
  .replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, '$1')
  .replace(/<(script|style)[\s\S]*?<\/\1>/gi, ' ')
  .replace(/<[^>]+>/g, ' ')
  .replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
  .replace(/&quot;/g, '"').replace(/&#0?39;|&apos;|&rsquo;|&lsquo;/g, "'").replace(/&ldquo;|&rdquo;/g, '"')
  .replace(/&mdash;/g, '—').replace(/&ndash;/g, '–')
  .replace(/&#(\d+);/g, (m, n) => String.fromCharCode(+n))
  .replace(/<(script|style)[\s\S]*?<\/\1>/gi, ' ').replace(/<\/?[a-z][^>]*>/gi, ' ')   // feeds often escape their HTML
  .replace(/\s+/g, ' ').trim();
// The article as its own paragraphs. Used only for a source whose fullText switch is on in Config.
const paragraphs = (xml, t) => {
  const m = xml.match(new RegExp('<' + t + '(?:\\s[^>]*)?>([\\s\\S]*?)</' + t + '>', 'i'));
  if (!m) return [];
  const html = m[1].replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, '$1')
    .replace(/&lt;/g, '<').replace(/&gt;/g, '>')
    .replace(/<(script|style|figure|figcaption|iframe)[\s\S]*?<\/\1>/gi, ' ');
  return html.split(/<\/p>|<br\s*\/?>\s*<br\s*\/?>|<\/h[1-6]>|<\/li>/i).map(decode).filter(p => p.length > 1);
};
// "none@none.com (Mansoor Malik)" -> "Mansoor Malik"
const person = s => { const m = /\(([^)]+)\)\s*$/.exec(s); return (m ? m[1] : s.includes('@') ? '' : s).trim(); };
const tag = (xml, t) => {
  const m = xml.match(new RegExp('<' + t + '(?:\\s[^>]*)?>([\\s\\S]*?)</' + t + '>', 'i'));
  return m ? decode(m[1]) : '';
};

const cut = Date.now() - cfg.hoursBack * 3600e3;
const seen = new Set();
const all = [];
$input.all().forEach((item, i) => {
  const feed = feeds[i] ? feeds[i].json : {};
  const xml = typeof item.json.data === 'string' ? item.json.data : '';
  (xml.match(/<item[\s>][\s\S]*?<\/item>/gi) || []).forEach(x => {
    const url = tag(x, 'link'), title = tag(x, 'title');
    if (!url || !title || seen.has(url)) return;
    const when = Date.parse(tag(x, 'pubDate'));
    if (when && when < cut) return;
    seen.add(url);
    const teaser = tag(x, 'description');
    const body = tag(x, 'content:encoded') || (teaser.length > 900 ? teaser : '');
    const full = (cfg.fullText || {})[feed.source] === true
      ? (paragraphs(x, 'content:encoded').length ? paragraphs(x, 'content:encoded') : paragraphs(x, 'description')) : [];
    // the article's first picture, only for a source whose pictures switch is on
    const pic = (cfg.pictures || {})[feed.source] === true
      ? ((x.match(/<media:(?:content|thumbnail)[^>]*\surl=["']([^"']+)["']/i) || x.match(/<enclosure[^>]*\surl=["']([^"']+\.(?:jpe?g|png|webp)[^"']*)["']/i)
          || x.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').match(/<img[^>]*\ssrc=["'](https?:[^"']+)["']/i) || [])[1] || '') : '';
    all.push({ ...(pic ? { image: pic.replace(/&amp;/g, '&') } : {}), source: feed.source, section: feed.section, title, url,
               author: person(tag(x, 'dc:creator') || tag(x, 'author')),
               teaser: teaser.slice(0, 300), body: body.slice(0, 9000), when: when || 0,
               ...(full.join(' ').length > 600 ? { paras: full } : {}) });
  });
});
if (!all.length) throw new Error('No stories came back from any feed. Check the feed addresses in Config.');
const candidates = all.sort((a, b) => b.when - a.when).slice(0, 160).map((c, i) => ({ id: i + 1, ...c }));

const pkt = new Date(Date.now() + 5 * 3600e3).toISOString();   // Pakistan time
const date = pkt.slice(0, 10), time = pkt.slice(11, 16);

const system = `You are the news editor of ExamPrep, a study app for candidates of Pakistan's competitive examinations (CSS, PMS, FPSC, PPSC, SPSC and similar). Each morning you decide what a candidate should read from the day's newspapers, so that they can stop reading everything else.

You are given today's candidate stories as a numbered list: source, section, headline, author and a short teaser. Choose from this list only, and refer to stories by their id.

How to choose
Score every story from 0 to 2 on each of five things, for a total out of 10:
1. Syllabus link: Current Affairs, Pakistan Affairs, International Relations, or a likely essay theme.
2. Shelf life: still useful in next year's examination, not a one-day story.
3. Facts and figures: statistics, reports, treaties, laws, dates or appointments that can be quoted.
4. Author authority: a senior diplomat, economist, jurist or bureaucrat, or the paper's own editorial.
5. Exam likelihood: could become an MCQ, a short question, an essay topic or a précis passage.
A score of 8 to 10 is "must_read". A score of 5 to 7 is "skim". Leave out anything below 5.

Preferences
- Editorials and opinion first, then analysis, then hard news with lasting facts.
- Dawn's editorials and Dawn's opinion columns of the day are always included: every one of them is a pick, "must_read" when it scores 8 or more and "skim" otherwise. This is the one exception to leaving out pieces below 5.
- Then add the best two to four opinion pieces and editorials of The Express Tribune.
- Then add Foreign Affairs pieces that bear on Pakistan, South Asia, the great powers or a likely essay theme.
- After those, hard news from Dawn first, then The Express Tribune.
- When two papers cover the same story, keep the better one only.
- Never choose city or metro news, letters to the editor, daily party gossip, talk-show quarrels, crime, showbiz, sport, or daily casualty counts.
- Return between ${cfg.minPicks} and ${cfg.maxPicks} picks. Fewer good ones are better than padding with weak ones.

The front-page summary
Separately, choose the headlines for the app's "News Summary": the 5 to 8 national stories and the 5 to 8 international stories a candidate should at least know happened today. These may include hard news that you did not pick for a full card. A story about Pakistan is national. Everything else, including Pakistan's dealings with other countries when the event is abroad, is international.`;

const list = candidates.map(c =>
  `${c.id}. [${c.source} · ${c.section}] ${c.title}${c.author ? ' — ' + c.author : ''}\n   ${c.teaser}`).join('\n');

const request = {
  model: cfg.model,
  max_tokens: 8000,
  fallbacks: 'default',
  system,
  messages: [{ role: 'user', content: `Today is ${date}. Here are the candidate stories.\n\n${list}` }],
  output_config: {
    effort: 'medium',
    format: { type: 'json_schema', schema: {
      type: 'object', additionalProperties: false, required: ['picks', 'national', 'international'],
      properties: {
        picks: { type: 'array', items: {
          type: 'object', additionalProperties: false, required: ['id', 'score', 'priority', 'reason'],
          properties: { id: { type: 'integer' }, score: { type: 'integer' },
                        priority: { type: 'string', enum: ['must_read', 'skim'] }, reason: { type: 'string' } } } },
        national: { type: 'array', items: { type: 'integer' } },
        international: { type: 'array', items: { type: 'integer' } },
      } } },
  },
};
return [{ json: { date, time, candidates, request } }];
