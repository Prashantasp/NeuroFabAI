import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import ts from 'typescript';

function client(fetch) {
  const source = readFileSync(new URL('./src/lib/api.ts', import.meta.url), 'utf8');
  const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } });
  const exports = {};
  vm.runInNewContext(outputText, { exports, process: { env: { NEXT_PUBLIC_API_URL: 'https://api.example.com/api/v1' } },
    fetch, Headers, Response, AbortSignal, DOMException, setTimeout, clearTimeout,
    document: { cookie: '' }, window: { localStorage: { getItem: () => null, removeItem() {} } } });
  return exports;
}

test('session restore calls API when its cookies are invisible on the frontend host', async () => {
  let calls = 0;
  const api = client(async (url, options) => {
    calls++;
    assert.equal(url, 'https://api.example.com/api/v1/auth/refresh');
    assert.equal(options.credentials, 'include');
    assert.ok(options.signal);
    return Response.json({ success: true, data: { access_token: 'new-token' } });
  });
  assert.equal(await api.api.restoreSession(), 'new-token');
  assert.equal(api.getAccessToken(), 'new-token');
  assert.equal(calls, 1);
});

test('concurrent restore calls rotate only once and invalid sessions clear access', async () => {
  let calls = 0;
  const api = client(async () => {
    calls++;
    await new Promise(resolve => setTimeout(resolve, 5));
    return Response.json({ success: false, error: { message: 'Session expired' } }, { status: 401 });
  });
  api.setAccessToken('stale-token');
  const results = await Promise.allSettled([api.api.restoreSession(), api.api.restoreSession()]);
  assert.ok(results.every(result => result.status === 'rejected'));
  assert.equal(calls, 1);
  assert.equal(api.getAccessToken(), null);
});
