async function request(path, signal, options = {}) {
  const response = await fetch(`/api${path}`, { ...options, signal, headers: { Accept: 'application/json', ...options.headers } });
  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error('The server returned an unreadable response.');
  }
  if (!response.ok) throw new Error(data.error?.message || `Request failed (${response.status}).`);
  return data;
}

export const getWork = (id, signal) => request(`/works/${id}`, signal);
export const getCard = (id, signal) => request(`/cards/${id}`, signal);
export const getBookCards = (workId, book, signal) => request(`/works/${workId}/books/${book}/cards`, signal);

export async function getInitialCard(signal) {
  const { works } = await request('/works', signal);
  const work = works.find((item) => /aeneid/i.test(item.title)) || works[0];
  if (!work) throw new Error('No literary works are available yet.');
  const directory = await request(`/works/${work.id}`, signal);
  const book = directory.books.find((item) => item.first_card_id != null);
  if (!book) throw new Error('No reading passages are available yet.');
  return getCard(book.first_card_id, signal);
}

export const getGloss = (range, signal) => request('/gloss', signal, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(range),
});
