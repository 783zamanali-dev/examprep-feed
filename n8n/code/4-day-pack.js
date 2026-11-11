// Joins what Claude wrote to the real headline, link and source of each story (these come
// from the feed, never from the model), and prepares the day pack for the feed repository.
const cfg = $('Config').first().json;
const prev = $('Candidates').first().json;
const plan = $('Write request').first().json;
const res = $input.first().json;
if (res.stop_reason === 'refusal' || res.stop_reason === 'max_tokens')
  throw new Error('Writing the day stopped early: ' + res.stop_reason);
const out = JSON.parse((res.content || []).filter(b => b.type === 'text').map(b => b.text).join(''));

const byId = new Map(prev.candidates.map(c => [c.id, c]));
const pick = new Map(plan.picks.map(p => [p.id, p]));

const cards = (out.cards || []).filter(c => pick.has(c.id)).map(c => {
  const src = byId.get(c.id), p = pick.get(c.id);
  return { ...(src.image ? { image: src.image } : {}), source: src.source, url: src.url, title: src.title, author: src.author, section: src.section,
           tags: c.tags, score: p.score, priority: p.priority, why: c.why, summary: c.summary,
           key_facts: c.key_facts, vocab: c.vocab,
           // the article itself, only for a must-read piece from a paper whose fullText switch is on
           ...(p.priority === 'must_read' && src.paras ? { text: src.paras } : {}) };
});
const line = s => { const src = byId.get(s.id); return { headline: s.headline, line: s.line, source: src.source, url: src.url }; };
const written = new Map((out.summary || []).filter(s => byId.has(s.id)).map(s => [s.id, s]));
const summary = {
  national: plan.headlines.national.filter(id => written.has(id)).map(id => line(written.get(id))),
  international: plan.headlines.international.filter(id => written.has(id)).map(id => line(written.get(id))),
};
const mcqs = (out.mcqs || []).filter(m => Array.isArray(m.options) && m.options.length === 4).slice(0, cfg.maxMcqs);
if (!cards.length) throw new Error('Claude returned no cards.');

const pack = { date: prev.date, time: prev.time, summary, cards, mcqs };
const file = `${prev.date}-${prev.time.replace(':', '')}.json`;
return [{ json: {
  file, cards: cards.length, mcqs: mcqs.length,
  github: { message: `Day pack ${prev.date}: ${cards.length} cards, ${mcqs.length} MCQs`,
            content: Buffer.from(JSON.stringify(pack, null, 1), 'utf8').toString('base64'),
            branch: cfg.branch },
} }];
