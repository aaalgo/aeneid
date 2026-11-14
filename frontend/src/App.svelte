<script>
  import { onMount, tick } from 'svelte';
  import { getCard, getInitialCard, getGloss } from './api.js';
  import TitlePane from './components/TitlePane.svelte';
  import CardReader from './components/CardReader.svelte';
  import ParsePanel from './components/ParsePanel.svelte';

  let card = $state(null);
  let mode = $state('english');
  let showGloss = $state(true);
  let selectedWord = $state(null);
  let loading = $state(true);
  let error = $state('');
  let retryId = null;
  let glosses = $state({});
  let glossLoading = $state(false);
  let glossError = $state('');
  let glossProgress = $state('');
  let glossController;
  let controller;

  async function loadGloss() {
    if (!card?.lines.length || glossLoading || loading) return;
    const passage = card;
    const current = new AbortController();
    glossController = current;
    glossLoading = true;
    glossError = '';
    const start = passage.lines[0].number;
    const end = passage.lines.at(-1).number;
    try {
      // Cards can exceed the API's 30-line limit. Keep each request bounded,
      // and retain completed batches if a later request fails.
      for (let first = start; first <= end; first += 30) {
        const last = Math.min(first + 29, end);
        const batch = passage.lines.filter(line => line.number >= first && line.number <= last);
        if (batch.every(line => glosses[line.id])) continue;
        glossProgress = `Loading glosses for lines ${first}–${last}…`;
        const result = await getGloss({ work_id: passage.work_id, book: passage.book, start: first, end: last }, current.signal);
        if (current.signal.aborted) return;
        glosses = { ...glosses, ...Object.fromEntries(result.lines.map(line => [line.id, line.gloss])) };
      }
    } catch (cause) {
      if (!current.signal.aborted) glossError = cause.message || 'Unable to load glosses. Please try again.';
    } finally {
      if (glossController === current) {
        glossLoading = false;
        glossProgress = '';
      }
    }
  }

  let requestNumber = 0;

  async function loadCard(id = null) {
    glossController?.abort();
    glossController = null;
    glossLoading = false;
    glossError = '';
    glossProgress = '';
    controller?.abort();
    controller = new AbortController();
    const currentRequest = ++requestNumber;
    retryId = id;
    selectedWord = null;
    loading = true;
    error = '';
    try {
      const result = await (id == null ? getInitialCard(controller.signal) : getCard(id, controller.signal));
      if (currentRequest !== requestNumber) return;
      card = result;
      selectedWord = null;
    } catch (cause) {
      if (currentRequest === requestNumber && cause.name !== 'AbortError') {
        error = cause.message || 'Unable to load this passage.';
      }
    } finally {
      if (currentRequest === requestNumber) loading = false;
    }
    if (currentRequest === requestNumber && !error) {
      // Render the passage first; gloss generation runs independently.
      await tick();
      if (currentRequest === requestNumber) void loadGloss();
    }
  }

  onMount(() => {
    loadCard();
    return () => {
      controller?.abort();
      glossController?.abort();
    };
  });
</script>

<div class="reader-app">
  <TitlePane {card} {mode} {loading} {showGloss} onglosstoggle={() => showGloss = !showGloss} onnavigate={loadCard} onmodechange={(value) => mode = value} />
  <CardReader {card} {mode} {showGloss} {loading} {error} {selectedWord}
    {glosses} {glossLoading} {glossError} {glossProgress} ongloss={loadGloss}
    onretry={() => loadCard(retryId)}
    onselect={(word) => selectedWord = word} />
  <ParsePanel {mode} {selectedWord} />
</div>
