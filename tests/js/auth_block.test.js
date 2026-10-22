// Frontend regression for the optional API keys (review R2/R3). Run by tests/test_dashboard_js.py with node.
// The auth block is extracted from index.html and evaluated here with stubbed fetch, localStorage and prompt.
const fs = require('fs');
const html = fs.readFileSync(process.argv[2], 'utf8');
const js = html.match(/<script>([\s\S]*)<\/script>/)[1];
const start = js.indexOf('const KEYS = {');
const end = js.indexOf('async function init() {');
const block = js.slice(start, end);

function makeEnv({storageThrows = false, prompts = [], responses = []} = {}) {
  const store = new Map();
  const calls = [];
  global.S = {cfg: {twin_url: 'http://twin:8001'}};
  global.localStorage = storageThrows
    ? {getItem() { throw new Error('no storage'); }, setItem() { throw new Error('no storage'); }}
    : {getItem: k => (store.has(k) ? store.get(k) : null), setItem: (k, v) => store.set(k, v)};
  global.window = {prompt: () => (prompts.length ? prompts.shift() : null)};
  global.fetch = async (url, options) => {
    calls.push({url, headers: (options && options.headers) || {}});
    const status = responses.length ? responses.shift() : 200;
    return {status, ok: status >= 200 && status < 300, json: async () => ({detail: status === 401 ? 'missing or invalid X-API-Key' : undefined, ok: true})};
  };
  return {store, calls};
}

const assert = (cond, msg) => { if (!cond) { console.error('FAIL: ' + msg); process.exit(1); } };

(async () => {
  // R2: stored key "old" is rejected, user enters "new", the retry must send "new"
  let env = makeEnv({prompts: ['new'], responses: [401, 200]});
  env.store.set('ecu_api_key', 'old');
  const api = new Function(block + '\nreturn {getJSON, withAuth, authHeaders, keyFor, setKey, serviceFor};')();
  await api.getJSON('/ask', {method: 'POST', headers: {'content-type': 'application/json'}, body: '{}'});
  assert(env.calls.length === 2, 'two requests expected');
  assert(env.calls[0].headers['x-api-key'] === 'old', 'first attempt uses stored key');
  assert(env.calls[1].headers['x-api-key'] === 'new', 'retry must use the newly entered key, got ' + env.calls[1].headers['x-api-key']);
  assert(env.calls[1].headers['content-type'] === 'application/json', 'caller headers preserved');

  // R3: separate keys per service; entering the twin key must not overwrite the copilot key; copilot key never goes to the twin
  env = makeEnv({prompts: ['twin-secret'], responses: [401, 200, 200]});
  env.store.set('ecu_api_key', 'copilot-secret');
  const api2 = new Function(block + '\nreturn {getJSON, authHeaders, keyFor};')();
  await api2.getJSON('http://twin:8001/faults', {method: 'POST'});
  assert(env.calls[0].headers['x-api-key'] === undefined, 'no copilot key sent to the twin');
  assert(env.calls[1].headers['x-api-key'] === 'twin-secret', 'twin retry uses the twin key');
  assert(env.store.get('ecu_api_key') === 'copilot-secret', 'copilot key untouched');
  assert(env.store.get('twin_api_key') === 'twin-secret', 'twin key stored separately');
  await api2.getJSON('/decisions', {method: 'POST'});
  assert(env.calls[2].headers['x-api-key'] === 'copilot-secret', 'copilot request uses copilot key');

  // storage unavailable: the entered key still survives in memory for the retry
  env = makeEnv({storageThrows: true, prompts: ['mem-key'], responses: [401, 200]});
  const api3 = new Function(block + '\nreturn {getJSON};')();
  await api3.getJSON('/ask', {method: 'POST'});
  assert(env.calls[1].headers['x-api-key'] === 'mem-key', 'in-memory key used on retry without storage');

  // a failed retry must surface as an error, not as success
  env = makeEnv({prompts: ['still-wrong'], responses: [401, 401]});
  const api4 = new Function(block + '\nreturn {getJSON};')();
  let threw = false;
  try { await api4.getJSON('/ask', {method: 'POST'}); } catch (e) { threw = /401/.test(e.message); }
  assert(threw, 'second 401 must throw');
  assert(env.calls.length === 2, 'no endless prompting');
  console.log('auth block ok');
})().catch(e => { console.error('ERROR', e); process.exit(1); });
