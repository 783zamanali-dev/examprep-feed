// Takes Claude's choices and asks it to write the day: one card per chosen story, the
// front-page summary lines, and the MCQs.
const cfg = $('Config').first().json;
const prev = $('Candidates').first().json;
const res = $input.first().json;
if (res.stop_reason === 'refusal' || res.stop_reason === 'max_tokens')
  throw new Error('Choosing the stories stopped early: ' + res.stop_reason);
const text = (res.content || []).filter(b => b.type === 'text').map(b => b.text).join('');
const choice = JSON.parse(text);

const byId = new Map(prev.candidates.map(c => [c.id, c]));
const picks = (choice.picks || []).filter(p => byId.has(p.id)).slice(0, cfg.maxPicks);
if (!picks.length) throw new Error('No story was chosen today.');
const headlines = { national: (choice.national || []).filter(id => byId.has(id)),
                    international: (choice.international || []).filter(id => byId.has(id)) };

const system = `You write the daily study material of ExamPrep, an app for candidates of Pakistan's competitive examinations (CSS, PMS, FPSC, PPSC and similar). Your readers are preparing for Current Affairs, Pakistan Affairs, essay and MCQ papers. Many read English as a second language, so write short, plain sentences.

You are given today's chosen articles, each with its id and the text its publisher released, plus a list of headlines for the front-page summary. Write three things.

1. A card for every chosen article
- "summary": 3 or 4 short sentences in your own words that give the argument or the news, so that a reader knows what the piece says and can decide whether to open the original.
- "why": one line on why it matters for the examination.
- "key_facts": 3 to 6 facts a candidate could quote: figures, dates, names, laws, treaties, reports. One fact per item, complete in itself.
- "vocab": up to 3 less common words from the piece that are worth learning, each with a simple meaning. Leave it empty when there are none.
- "tags": 1 or 2 syllabus areas, for example Current Affairs, Pakistan Affairs, Foreign Policy, Economy, Environment, Governance, Security, International Relations, Science and Technology.

2. The front-page summary
For every headline id you are given, one entry: "headline", a short headline in your own words, and "line", one sentence of at most 25 words saying what happened and why it matters.

3. MCQs for the Current Affairs section
Write between ${cfg.minMcqs} and ${cfg.maxMcqs} MCQs from the facts in today's articles. Write as many as the day's solid facts support and no more: a quiet day gets fewer.
- Each tests one durable fact: who, what, when, where, how much, which body or law. Never test an opinion or a writer's argument.
- The question must stand alone months later. Say "In November 2026, which country …", never "according to the article" or "today".
- Four options, all plausible and of the same kind, exactly one correct. Put the correct option in a different position from question to question.
- "explanation": one or two sentences giving the fact and a little context, ending with the source name in brackets.
- "difficulty": Easy, Medium or Hard. "topic": one of Pakistan: Politics, Pakistan: Economy, Pakistan: Foreign Policy, International Affairs, Organisations and Treaties, Environment, Science and Technology, Appointments and Awards.

Rules that protect the reader and the newspapers
- Every fact must come from the text you were given. If you are not sure a figure or name is in the text, leave it out. Do not add facts from memory, because the reader will memorise what you write.
- Write everything in your own words. Never copy a sentence from an article. At most one short quotation per card, under 25 words, inside quotation marks.
- An article marked TEASER ONLY came with just its headline and a one-line summary. Write a shorter card from what those lines say, begin its summary with "From the published summary:", and write no MCQ from it.
- Refer to every article and headline by the id you were given.`;

const articles = picks.map(p => {
  const c = byId.get(p.id);
  const body = c.body && c.body.length > 600 ? c.body : '';
  return `=== ARTICLE id ${c.id} · ${c.source} · ${c.section}${c.author ? ' · ' + c.author : ''}${body ? '' : ' · TEASER ONLY'} ===\n${c.title}\n${body || c.teaser}`;
}).join('\n\n');
const heads = ['national', 'international'].map(k =>
  `${k.toUpperCase()}\n` + headlines[k].map(id => { const c = byId.get(id); return `${id}. ${c.title} (${c.source}) — ${c.teaser}`; }).join('\n')).join('\n\n');

const str = { type: 'string' };
const request = {
  model: cfg.model,
  max_tokens: 16000,
  fallbacks: 'default',
  system,
  messages: [{ role: 'user', content: `Today is ${prev.date}.\n\nCHOSEN ARTICLES\n\n${articles}\n\nHEADLINES FOR THE FRONT-PAGE SUMMARY\n\n${heads}` }],
  output_config: {
    effort: 'medium',
    format: { type: 'json_schema', schema: {
      type: 'object', additionalProperties: false, required: ['cards', 'summary', 'mcqs'],
      properties: {
        cards: { type: 'array', items: {
          type: 'object', additionalProperties: false, required: ['id', 'summary', 'why', 'key_facts', 'vocab', 'tags'],
          properties: { id: { type: 'integer' }, summary: str, why: str,
            key_facts: { type: 'array', items: str },
            vocab: { type: 'array', items: { type: 'object', additionalProperties: false, required: ['word', 'meaning'], properties: { word: str, meaning: str } } },
            tags: { type: 'array', items: str } } } },
        summary: { type: 'array', items: {
          type: 'object', additionalProperties: false, required: ['id', 'headline', 'line'],
          properties: { id: { type: 'integer' }, headline: str, line: str } } },
        mcqs: { type: 'array', items: {
          type: 'object', additionalProperties: false, required: ['q', 'options', 'answer', 'explanation', 'difficulty', 'topic'],
          properties: { q: str, options: { type: 'array', items: str },
            answer: { type: 'string', enum: ['A', 'B', 'C', 'D'] }, explanation: str,
            difficulty: { type: 'string', enum: ['Easy', 'Medium', 'Hard'] }, topic: str } } },
      } } },
  },
};
return [{ json: { picks, headlines, request } }];
