import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { latinSegments } from '../src/latinTokens.js';
const source = fs.readFileSync(new URL('../src/App.svelte', import.meta.url), 'utf8')
  .split('<script>')[1].split('</script>')[0].replace(/^  import .*;\n/gm, '');
const passage = { id: 1, work_id: 1, book: 1, lines: Array.from({ length: 65 }, (_, i) => ({ id: i + 1, number: i + 1 })) };
const calls = [];
const sandbox = { AbortController, onMount: () => {}, tick: () => Promise.resolve(), $state: x => x,
  getCard: async () => ({ ...passage, id: 2 }), getInitialCard: async () => passage,
  getGloss: async (range) => { calls.push(range); return { lines: Array.from({ length: range.end - range.start + 1 }, (_, i) => ({ id: range.start + i, gloss: [{ index: 0, token: 'Arma', english: 'arms' }] })) }; },
};
vm.createContext(sandbox);
vm.runInContext(source + '\nglobalThis.test = { loadCard, loadGloss, setCard: value => {card = value; loading = false;}, snapshot: () => ({ loading, glosses, glossLoading, glossError, glossProgress, card }) };', sandbox);
const t = sandbox.test;
const originalProvider = sandbox.getGloss;
let finishFirstBatch;
sandbox.getGloss = range => new Promise(resolve => {
  finishFirstBatch = async () => resolve(await originalProvider(range));
});
await t.loadCard();
assert.equal(t.snapshot().card.id, passage.id, 'passage is available before glosses');
assert.equal(t.snapshot().loading, false, 'passage loading does not wait for glosses');
assert.equal(t.snapshot().glossLoading, true, 'gloss loading starts automatically');
assert.equal(Object.keys(t.snapshot().glosses).length, 0);
sandbox.getGloss = originalProvider;
await finishFirstBatch();
while (t.snapshot().glossLoading) await new Promise(resolve => setImmediate(resolve));
assert.deepEqual(calls.map(r => [r.start,r.end]), [[1,30],[31,60],[61,65]]);
assert.equal(Object.keys(t.snapshot().glosses).length, 65);
await t.loadGloss();assert.equal(calls.length,3,'repeat skips already loaded glosses');
await t.loadCard(2);await t.loadGloss();assert.equal(calls.length,3,'navigation preserves known glosses');
const later = { ...passage, id: 3, lines: passage.lines.map(l => ({ id: l.id + 100, number: l.number + 100 })) };
t.setCard(later);
let attempt = 0;
sandbox.getGloss = async range => {
  if (++attempt === 2) throw new Error('Provider unavailable');
  return { lines: Array.from({ length: range.end - range.start + 1 }, (_, i) => ({ id: range.start + i, gloss: [] })) };
};
await t.loadGloss();
assert.equal(t.snapshot().glossError,'Provider unavailable');
assert.equal(t.snapshot().glossLoading,false);
assert.ok(t.snapshot().glosses[101]);assert.equal(t.snapshot().glosses[131], undefined);
sandbox.getGloss = async range => ({ lines: Array.from({ length: range.end - range.start + 1 }, (_, i) => ({ id: range.start + i, gloss: [] })) });
await t.loadGloss();assert.equal(t.snapshot().glossError,'');assert.ok(t.snapshot().glosses[165]);
let complete;
sandbox.getGloss = () => new Promise(resolve => complete = resolve);
t.setCard({ ...passage, lines: [{ id: 999, number: 999 }] });
const pending = t.loadGloss();await t.loadCard(2);
complete({ lines: [{ id: 999, gloss: [] }] });await pending;
assert.equal(t.snapshot().glosses[999], undefined, 'aborted response cannot update another passage');
const text = '“Arma, virumque cano; mene\' l’ora a\u0304rma!”';
const segments = latinSegments(text);
assert.equal(segments.map(s=>s.text).join(''), text);
assert.deepEqual(segments.filter(s=>s.index != null).map(s=>s.index), [0,1,2,3,4,5]);
assert.deepEqual(segments.filter(s=>s.index != null).map(s=>s.text), ['Arma','virumque','cano',"mene'",'l’ora','a\u0304rma']);
const gloss = segments.filter(s=>s.index != null).map(s=>({index:s.index,token:s.text,english:'meaning'}));
assert.equal(latinSegments(text,gloss).map(s=>s.text).join(''),text);
assert.ok(latinSegments(text,gloss).filter(s=>s.index!=null).every(s=>s.english==='meaning'));
let request;
globalThis.fetch = async (url, options) => { request={url,...options}; return {ok:true,json:async()=>({lines:[]})}; };
const { getGloss } = await import('../src/api.js');
await getGloss({work_id:1,book:1,start:1,end:7});
assert.equal(request.url,'/api/gloss');assert.equal(request.method,'POST');
assert.equal(request.headers['Content-Type'],'application/json');assert.equal(JSON.parse(request.body).end,7);
globalThis.fetch = async () => ({ok:false,json:async()=>({error:{message:'Generation unavailable'}})});
await assert.rejects(getGloss({}), /Generation unavailable/);
console.log('UI logic checks passed: automatic nonblocking generation, batching, reuse, partial failure/retry, navigation races, token identity, POST and API errors.');
