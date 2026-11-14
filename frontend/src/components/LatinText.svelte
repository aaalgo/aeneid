<script>
  import LatinWord from './LatinWord.svelte';
  import { latinSegments } from '../latinTokens.js';
  import { selectLatinWord } from '../morphology.js';
  let { lines, selectedWord, onselect, glosses, showGloss } = $props();
</script>

<div class="latin-text" lang="la">
  {#each lines as line (line.id)}
    {@const segments = latinSegments(line.latin, glosses[line.id])}
    <div class="verse-line">
      <span class="line-number" aria-label={`Line ${line.number}`}>{line.number}</span>
      <span class="verse-content">{#each segments as segment, position}{#if segment.index != null}<LatinWord text={segment.text} gloss={segment.english} {showGloss} selected={selectedWord?.lineId === line.id && selectedWord?.index === segment.index} onclick={() => onselect(selectLatinWord(line, segments, position))} />{:else}{segment.text}{/if}{/each}</span>
    </div>
  {:else}
    <p>No Latin lines are available for this passage.</p>
  {/each}
</div>
