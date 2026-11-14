<script>
  let { text, gloss = null, showGloss = true, selected = false, onclick } = $props();
</script>
<button class="latin-word" class:selected class:gloss-hidden={!showGloss} aria-label={showGloss && gloss ? `${text}: ${gloss}` : text} aria-pressed={selected} {onclick}>
  <span>{text}</span>
  {#if showGloss}
  <span class="word-gloss" lang="en" aria-hidden={gloss == null ? 'true' : undefined}>{gloss ?? '\u00a0'}</span>
  {/if}
</button>
