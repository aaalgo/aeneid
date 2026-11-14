import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { compile } from 'svelte/compiler';
import { render } from 'svelte/server';
import { latinSegments } from '../src/latinTokens.js';
import { selectLatinWord } from '../src/morphology.js';

const line = { id: 5, number: 8, latin: '“Et, arma; et a\u0304rma!”', morphology: [
  { word: 'et', parse: 'first' }, { word: 'arma', parse: '  free text;\nunchanged  ' },
  { word: 'ET', parse: 'second' }, { word: 'ārma', parse: 'unicode' },
] };
const segments = latinSegments(line.latin);
const choose = (text, occurrence = 0, data = line) => selectLatinWord(data, segments,
  segments.map((s, i) => ({...s, i})).filter(s => s.text === text)[occurrence].i);
assert.equal(segments.map(s => s.text).join(''), line.latin);
assert.equal(choose('Et').parse, 'first');
assert.equal(choose('et').parse, 'second');
assert.equal(choose('arma').parse, '  free text;\nunchanged  ');
assert.equal(choose('a\u0304rma').parse, 'unicode');
for (const morphology of [null, {}, 'bad', [], [null, {}, {word: 2}], [{word:'arma',parse:''}], [{word:'arma',parse:42}], [{word:'arma',parse:'  '}]]) {
  assert.equal(choose('arma', 0, {...line, morphology}).parse, null);
}
assert.equal(choose('et', 0, {...line, morphology:[{word:'et',parse:'ambiguous'}]}).parse, null);
assert.equal(selectLatinWord({...line, morphology:[{word:'ARMA',parse:'punctuation'}]},
  [{text:'“Arma,”',index:0}], 0).parse, 'punctuation');

// Render the real panel in both modes, including stale Latin selection in English.
const panelSource = fs.readFileSync(new URL('../src/components/ParsePanel.svelte', import.meta.url), 'utf8');
const panelCode = compile(panelSource, {generate:'server'}).js.code;
// Resolve Svelte imports from the project's node_modules.
const panelPath = new URL('./.parse-panel-test.mjs', import.meta.url);
fs.writeFileSync(panelPath, panelCode);
let Panel;
try { ({default: Panel} = await import(panelPath.href)); }
finally { fs.unlinkSync(panelPath); }
const output = (mode, selectedWord) => render(Panel, {props:{mode,selectedWord}}).body;
assert.match(output('latin', choose('et')), /second/);
assert.match(output('latin', {text:'absent',parse:null}), /Morphological analysis unavailable/);
assert.match(output('latin', null), /Select a Latin word/);
assert.match(output('english', choose('et')), /English passage explanation will appear here/);
assert.doesNotMatch(output('english', choose('et')), /second|Morphological parse/);

const appSource = fs.readFileSync(new URL('../src/App.svelte', import.meta.url), 'utf8');
const script = appSource.split('<script>')[1].split('</script>')[0].replace(/^  import .*;\n/gm, '');
const context = {AbortController, onMount:()=>{}, tick:async()=>{}, $state:x=>x,
  getCard:async()=>({id:2,lines:[]}), getInitialCard:async()=>({id:1,lines:[]})};
vm.createContext(context);
vm.runInContext(script + '\nglobalThis.test = {loadCard, select: value => selectedWord=value, selected:()=>selectedWord};', context);
context.test.select(choose('et'));
await context.test.loadCard(2);
assert.equal(context.test.selected(), null);
console.log('Morphology checks passed: lookup, repeated words, Unicode, malformed data, panel modes, navigation reset.');
