<script>
  let { mode, selectedWord } = $props();
</script>

<aside class="parse-panel" aria-labelledby="explanation-title">
  <div class="panel-content">
    <h2 id="explanation-title">{mode === 'english' ? 'Passage explanation' : 'Morphological parse'}</h2>
    <div aria-live="polite">
      {#if mode === 'english'}
        <p>English passage explanation will appear here.</p>
      {:else if selectedWord}
        <p class="selected-word" lang="la">{selectedWord.text}<span>Line {selectedWord.lineNumber}</span></p>
        <p class="parse-text">{selectedWord.parse ?? 'Morphological analysis unavailable.'}</p>
      {:else}
        <p>Select a Latin word to view its morphological analysis.</p>
      {/if}
    </div>
  </div>
</aside>
