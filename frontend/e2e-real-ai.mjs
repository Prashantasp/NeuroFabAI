/** Opt-in browser verification using the configured, real AI provider. */
import { chromium } from 'playwright';
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs';
import { resolve } from 'node:path';
import assert from 'node:assert/strict';

if (process.env.RUN_REAL_AI_E2E !== '1') throw new Error('Set RUN_REAL_AI_E2E=1; this test makes paid AI requests.');
const APP = process.env.APP_URL || 'http://localhost:3000';
const out = resolve('test-results/real-ai');
mkdirSync(out, { recursive: true });
const statePath = resolve(out, 'account.json');
const state = existsSync(statePath) ? JSON.parse(readFileSync(statePath, 'utf8')) : {
  email: `realai_${Date.now()}@neurofab-verify.example.com`, password: 'Correct-Horse-9',
};
writeFileSync(statePath, JSON.stringify(state, null, 2));
const report = { checks: [], questions: [], errors: [] };
const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const page = await context.newPage();
page.setDefaultTimeout(20000);
let authHeaders = {}, apiBase;
page.on('request', request => {
  if (request.headers()['x-workspace-id']) {
    authHeaders = { authorization: request.headers().authorization, 'x-workspace-id': request.headers()['x-workspace-id'] };
    apiBase = request.url().split('/api/v1')[0] + '/api/v1';
  }
});
page.on('pageerror', error => report.errors.push(error.message));
const check = (name, detail) => { report.checks.push({ name, detail }); console.log('PASS', name, detail || ''); };
const get = async path => {
  const response = await context.request.get(apiBase + path, { headers: authHeaders });
  assert.equal(response.status(), 200, await response.text());
  return (await response.json()).data;
};
try {
  if (!state.registered) {
    await page.goto(APP + '/register');
    await page.fill('#full-name', 'Real AI Verification');
    await page.fill('#email', state.email);
    await page.fill('#password', state.password);
    await page.fill('#confirm', state.password);
    await page.getByRole('button', { name: /create account/i }).click();
    await page.waitForURL(/\/login/, { timeout: 30000 });
    state.registered = true;
    writeFileSync(statePath, JSON.stringify(state, null, 2));
    check('register');
  }
  await page.goto(APP + '/login');
  await page.fill('#email', state.email);
  await page.fill('#password', state.password);
  await page.getByRole('button', { name: /^sign in$/i }).click();
  await page.waitForURL(/\/dashboard/, { timeout: 30000 });
  await page.getByRole('heading', { level: 1 }).waitFor();
  check('login');
  await page.reload();
  await page.getByRole('heading', { level: 1 }).waitFor();
  assert.ok(page.url().includes('/dashboard'));
  check('session survives reload');
  await page.goto(APP + '/hub');
  await page.getByRole('button', { name: /^upload pdf$/i }).waitFor();
  if (!state.documentId) {
    const uploaded = page.waitForResponse(response => response.url().endsWith('/documents/upload') && response.request().method() === 'POST');
    await page.locator('input[type=file]').setInputFiles(resolve('fixtures/verification-pump-manual.pdf'));
    const response = await uploaded;
    assert.equal(response.status(), 201, await response.text());
    state.documentId = (await response.json()).data.id;
    writeFileSync(statePath, JSON.stringify(state, null, 2));
    check('PDF uploaded through UI', state.documentId);
  }
  if (process.env.REPROCESS_DOCUMENT === '1') {
    const pending = page.waitForResponse(response => response.url().endsWith('/reprocess'));
    await page.getByRole('button', { name: /^Reprocess / }).first().click();
    assert.equal((await pending).status(), 200);
    check('reprocess through UI');
  }
  let doc, lastStage;
  const deadline = Date.now() + 240000;
  do {
    doc = await get('/documents/' + state.documentId);
    if (doc.current_stage !== lastStage) { console.log('PROCESSING', doc.current_stage); lastStage = doc.current_stage; }
    if (['READY','FAILED'].includes(doc.status)) break;
    await page.waitForTimeout(2000);
  } while (Date.now() < deadline);
  report.document = doc;
  assert.equal(doc.status, 'READY', JSON.stringify({ status: doc.status, failure: doc.failure_reason }));
  assert.equal(doc.graph_status, 'COMPLETED', doc.failure_reason || 'Graph incomplete');
  assert.equal(doc.embedding_status, 'COMPLETED');
  assert.equal(doc.metadata_json?.performance?.embedding_provider, 'gemini');
  check('real AI ingestion', `${doc.chunk_count} chunks, ${doc.entity_count} entities, ${doc.relationship_count} relationships`);
  await page.screenshot({ path: resolve(out, '01-document-ready.png'), fullPage: true });
  const topology = await get('/graph/topology');
  report.graph = topology;
  assert.ok(topology.nodes.some(n => /NF.?731/i.test(n.canonical_name)));
  assert.ok(topology.nodes.some(n => /BR.?731/i.test(n.canonical_name)));
  assert.ok(topology.edges.length > 0);
  assert.ok(topology.nodes.every(n => n.source_document_id === state.documentId));
  const ids = new Set(topology.nodes.map(n => n.id));
  assert.ok(topology.edges.every(e => ids.has(e.source) && ids.has(e.target) && e.source_document_id === state.documentId));
  assert.ok(topology.edges.some(e => /strainer/i.test(e.source) && /cavitation/i.test(e.target) && e.type === 'CAUSES'),
    'The explicit blocked-strainer cause must be present');
  assert.ok(topology.edges.some(e => /cavitation/i.test(e.source) && /vibration/i.test(e.target) && e.type === 'CAUSES'),
    'Causal direction must match the PDF');
  check('graph identities, causal direction, relationships and document provenance');
  await page.goto(APP + '/graph');
  await page.locator('canvas').first().waitFor();
  await page.waitForTimeout(1500);
  await page.screenshot({ path: resolve(out, '02-graph.png'), fullPage: true });
  check('graph rendered');
  await page.goto(APP + '/copilot');
  const questions = [
    ['What is the rated operating pressure of Pump NF-731?', /6\.4\s*bar/i],
    ['How often should bearing BR-731 be lubricated, and which lubricant should be used?', /240/],
    ['What motor voltage does Pump NF-731 require?', /not (?:specif|provid|establish)|does not|no .*voltage|insufficient/i],
  ];
  for (const [query, expected] of questions) {
    await page.locator('#copilot-input').fill(query);
    const pending = page.waitForResponse(response => response.url().endsWith('/chat/stream'), { timeout: 180000 });
    await page.getByRole('button', { name: 'Send question' }).click();
    const response = await pending;
    const body = await response.text();
    const frame = body.split('\n\n').find(frame => frame.startsWith('event: decision'));
    const payload = frame ? JSON.parse(frame.split('\n').filter(line => line.startsWith('data:')).map(line => line.slice(5)).join('\n')) : null;
    report.questions.push({ query, payload, ...(payload ? {} : { stream: body }) });
    writeFileSync(resolve(out, 'report.json'), JSON.stringify(report, null, 2));
    assert.ok(payload, body);
    const decision = payload.decision;
    console.log('ANSWER', query, JSON.stringify(decision));
    assert.match([decision.executive_summary, ...decision.supporting_evidence, decision.recommended_action].join(' '), expected);
    if (!query.includes('voltage')) {
      assert.equal(decision.evidence_status, 'references_checked');
      assert.ok(decision.citations.length > 0);
      assert.ok(decision.citations.every(c => c.document_id === state.documentId));
      if (query.includes('lubricated')) assert.match(JSON.stringify(decision), /LUBE-X7/i);
    }
    assert.equal(decision.confidence, null);
    assert.equal(decision.risk_level, null, "The manual does not provide a risk rating");
    await page.getByRole('button', { name: 'Copy answer' }).last().waitFor({ timeout: 15000 });
    check('Copilot question', query);
  }
  await page.screenshot({ path: resolve(out, '03-copilot.png'), fullPage: true });
  assert.deepEqual(report.errors, []);
  check('no browser exceptions');
} catch (error) {
  report.failure = error.stack;
  await page.screenshot({ path: resolve(out, 'failure.png'), fullPage: true }).catch(() => {});
  console.error(error.message);
  process.exitCode = 1;
} finally {
  writeFileSync(resolve(out, 'report.json'), JSON.stringify(report, null, 2));
  await browser.close();
}
