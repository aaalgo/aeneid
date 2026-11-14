<script>
  import EnglishText from './EnglishText.svelte';
  import LatinText from './LatinText.svelte';
  import AlignmentLayer from './AlignmentLayer.svelte';
  let { card, mode, showGloss, loading, error, selectedWord, onretry, onselect, glosses, glossLoading, glossError, glossProgress, ongloss } = $props();
  let textPane;
  $effect(() => {
    const id = card?.id;
    if (id != null && textPane) textPane.scrollTop = 0;
  });
</script>

<main class="card-reader" aria-label="Passage reader">
  <!-- Keyboard focus lets readers scroll the passage without moving the whole page. -->
  <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
  <section class="text-pane" bind:this={textPane} aria-label="Current passage" aria-busy={loading} tabindex="0">
    {#if loading}
      <div class="status" role="status">Loading passage…</div>
    {:else if error}
      <div class="status"><p role="alert">{error}</p><button onclick={onretry}>Retry</button></div>
    {:else if card}
      <div class="passage">
        {#if mode === 'english'}
          <EnglishText text={card.english} />
        {:else}
          {#if showGloss}
          <div class="gloss-toolbar">
            <span role="status">{glossLoading ? glossProgress : card.lines.length && card.lines.every(line => glosses[line.id]) ? 'AI-generated English glosses.' : ''}</span>
            {#if glossError}
              <span class="gloss-error" role="alert">{glossError}</span>
              <button onclick={ongloss}>Retry glosses</button>
            {/if}
          </div>
          {/if}
          <LatinText lines={card.lines} {selectedWord} {onselect} {glosses} {showGloss} />
        {/if}
        <AlignmentLayer />
      </div>
    {/if}
  </section>
</main>
