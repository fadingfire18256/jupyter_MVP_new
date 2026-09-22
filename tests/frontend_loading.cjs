// Real asynchronous boundaries, mocked responses: no DOM, network, or API keys.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const code = fs.readFileSync(path.join(__dirname, '../server/static/data.js'), 'utf8');

async function check(kind, outcome, stale = true, delayJson = false) {
  let resolve, reject, missingCalls = 0, renders = 0;
  const pending = new Promise((yes, no) => { resolve = yes; reject = no; });
  const store = { titles: ['A'], movies: [], loading: true, enriching: false };
  const state = { loadGeneration: 0, keyMissing: { tmdb: false },
    cinemas: { demo: store }, genres: {}, genreError: null };
  const response = { ok: outcome !== '401', json: async () => outcome === '401'
    ? { need_key: 'tmdb' } : { movies: ['new title'], results: [{ id: 1 }], genres: [{ id: 1, name: 'new genre' }] } };
  const context = vm.createContext({ state, API: '/api', TMDB_CONCURRENCY: 4,
    fetch: () => delayJson ? Promise.resolve({ ...response, json: () => pending }) : pending,
    render: () => renders++, scheduleRender: () => renders++,
    noteMissingKey: (data) => { if (data.need_key) { missingCalls++; state.keyMissing.tmdb = true; return true; } return false; } });
  vm.runInContext(code, context);
  const call = kind === 'genres' ? context.loadGenres()
    : kind === 'cinema' ? context.loadCinema({ key: 'demo' })
      : context.enrichTitles({ key: 'demo' }, store);
  await Promise.resolve();
  const priorRenders = renders;
  const priorStore = JSON.stringify(store);
  if (stale) state.loadGeneration++;
  if (outcome === 'reject') reject(new Error('old request failed'));
  else resolve(delayJson ? await response.json() : response);
  await call;
  if (stale) {
    assert.equal(missingCalls, 0, `${kind}: old response invoked missing-key handler`);
    assert.equal(state.keyMissing.tmdb, false);
    assert.equal(state.genreError, null);
    assert.equal(JSON.stringify(state.genres), '{}');
    assert.equal(JSON.stringify(store), priorStore, `${kind}: old response changed store`);
    assert.equal(renders, priorRenders, `${kind}: old response triggered render`);
  } else {
    assert.equal(missingCalls, 1, 'current 401 must still report a missing key');
    assert.equal(state.keyMissing.tmdb, true);
  }
}

(async () => {
  let count = 0;
  for (const kind of ['cinema', 'enrich', 'genres']) {
    for (const outcome of ['success', '401', 'reject']) {
      for (const delayJson of [false, true]) {
        await check(kind, outcome, true, delayJson);
        count++;
      }
    }
  }
  await check('enrich', '401', false);
  console.log(`${count + 1} frontend loading scenarios passed`);
})().catch(error => { console.error(error); process.exitCode = 1; });
