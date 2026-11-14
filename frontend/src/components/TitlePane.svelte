<script>
  import { getWork, getBookCards } from '../api.js';

  let { card, mode, loading, onnavigate, onmodechange, showGloss, onglosstoggle } = $props();
  const roman = (number) => ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI', 'XII'][number - 1] || number;
  let books = $state([]);
  let cards = $state([]);
  let directoryLoading = $state(false);
  let directoryError = $state('');
  let retry = $state(0);
  let directoryKey = $derived(card ? `${card.work_id}/${card.book}` : null);

  $effect(() => {
    const key = directoryKey;
    retry;
    if (!key) return;
    const [workId, book] = key.split('/').map(Number);
    const controller = new AbortController();
    directoryLoading = true;
    directoryError = '';
    books = [];
    cards = [];
    Promise.all([getWork(workId, controller.signal), getBookCards(workId, book, controller.signal)])
      .then(([work, directory]) => {
        if (controller.signal.aborted) return;
        books = work.books;
        cards = directory.cards;
      })
      .catch((error) => {
        if (!controller.signal.aborted) directoryError = error.message;
      })
      .finally(() => {
        if (!controller.signal.aborted) directoryLoading = false;
      });
    return () => controller.abort();
  });

  function selectBook(event) {
    const book = books.find((item) => item.number === Number(event.currentTarget.value));
    if (book?.first_card_id != null) onnavigate(book.first_card_id);
  }

</script>

<header class="title-pane">
  <div class="title-location">
    <h1>Aeneid</h1>
    {#if card}
      <div class="location-selectors" aria-busy={directoryLoading}>
        <select aria-label="Book" value={card.book} disabled={loading || directoryLoading || !!directoryError} onchange={selectBook}>
          {#if books.length}
            {#each books as book (book.number)}
              <option value={book.number} disabled={book.first_card_id == null}>Book {roman(book.number)}</option>
            {/each}
          {:else}
            <option value={card.book}>Book {roman(card.book)}</option>
          {/if}
        </select>
        <select aria-label="Card line range" value={card.id} disabled={loading || directoryLoading || !!directoryError} onchange={(event) => onnavigate(Number(event.currentTarget.value))}>
          {#if cards.length}
            {#each cards as item (item.id)}
              <option value={item.id}>Lines {item.latin_start}–{item.latin_end}</option>
            {/each}
          {:else}
            <option value={card.id}>Lines {card.latin_start}–{card.latin_end}</option>
          {/if}
        </select>
        {#if directoryError}
          <button class="directory-retry" title={directoryError} onclick={() => retry += 1}>Retry navigator</button>
          <span class="sr-only" role="alert">Unable to load the book and card directory. {directoryError}</span>
        {/if}
      </div>
    {/if}
  </div>
  <nav class="passage-navigation" aria-label="Passage navigation">
    <button disabled={loading || card?.prev == null} onclick={() => onnavigate(card.prev)}>← Previous</button>
    <button disabled={loading || card?.next == null} onclick={() => onnavigate(card.next)}>Next →</button>
  </nav>
  <div class="mode-switch" role="group" aria-label="Reading options">
    <button aria-pressed={mode === 'english'} onclick={() => onmodechange('english')}>English</button>
    <button aria-pressed={mode === 'latin'} onclick={() => onmodechange('latin')}>Latin</button>
    <button aria-pressed={showGloss} onclick={onglosstoggle}>Gloss</button>
  </div>
</header>
