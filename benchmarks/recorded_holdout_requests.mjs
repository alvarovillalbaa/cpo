// Reconstruct Responses payloads through the archived runtime with a local transport stub.
import { createHash } from 'node:crypto';
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import net from 'node:net';
import { dirname, join, resolve } from 'node:path';
import tls from 'node:tls';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { parseArgs } from 'node:util';

const sha256 = bytes => createHash('sha256').update(bytes).digest('hex');
const json = path => JSON.parse(readFileSync(path, 'utf8'));
const sourcePlanDigest = '4023fb794d1488f61a6518e28214423ed904b0f68b6ca67ea524af01aa3a3f84';
const model = 'gpt-6.2-sol';
const maximumOutputTokens = 384;
const origins = ['strict', 'fields', 'hybrid'];

export function finalistSlots(audit, cases) {
  const prompts = [...new Set(audit.distinctDirections.flatMap(pair => [pair.cpo, pair.control]))].sort();
  const knownIds = new Set(cases.map(row => row.id));
  if (knownIds.size !== cases.length || !cases.length || !prompts.length) {
    throw new Error('Expected distinct holdout cases and observed finalists');
  }
  for (const [prompt, ids] of Object.entries(audit.missingPromptCases)) {
    if (!prompts.includes(prompt) || ids.length !== new Set(ids).size || ids.some(id => !knownIds.has(id))) {
      throw new Error('Missing evidence must name a finalist and unique holdout cases');
    }
  }
  return [...cases].sort((a, b) => a.id < b.id ? -1 : a.id === b.id ? 0 : 1).flatMap((row, index) => {
    const offset = index % prompts.length;
    const rotated = [...prompts.slice(offset), ...prompts.slice(0, offset)];
    return rotated.map(prompt => ({ prompt, case: row.id,
      missing: audit.missingPromptCases[prompt]?.includes(row.id) ?? false }));
  });
}

function loadArchive(root, sourcePlan, audit) {
  const source = readFileSync(sourcePlan);
  if (sha256(source) !== sourcePlanDigest) throw new Error('The sealed archive source manifest differs');
  const { outage: files } = JSON.parse(source).taskSources;
  for (const [file, fingerprint] of Object.entries(files)) {
    if (sha256(readFileSync(join(root, file))) !== fingerprint) throw new Error('A sealed outage source file differs');
  }

  const prompts = new Map();
  const reference = [];
  let rows;
  for (const origin of origins) {
    const plan = json(join(root, `outage-${origin}-plan.json`));
    if (plan.model !== model || plan.tokenCaps.candidate !== maximumOutputTokens) {
      throw new Error('Original outage candidate settings disagree');
    }
    rows ??= plan.datasets.holdout;
    if (JSON.stringify(rows) !== JSON.stringify(plan.datasets.holdout)) throw new Error('Holdout inputs disagree across source arms');
    const directory = join(root, `outage-${origin}`);
    const result = json(join(directory, 'results.json'));
    for (const entry of [result.holdoutBaseline, result.holdoutCandidate, ...result.rounds.flatMap(round => round.arms)]) {
      if (sha256(JSON.stringify(entry.prompt)) !== entry.promptSha256) throw new Error('Archived prompt fingerprint differs');
      prompts.set(entry.promptSha256, entry.prompt);
    }
    const events = readFileSync(join(directory, 'events.jsonl'), 'utf8').trim().split('\n').map(line => JSON.parse(line));
    const usage = new Map(events.filter(event => event.type === 'provider-usage').map(event => [event.responseId, event]));
    const reserves = new Map(events.filter(event => event.type === 'provider-reservation').map(event => [event.id, event.amount]));
    for (const event of events.filter(event => event.type === 'evaluation' && event.split === 'holdout')) {
      const receipt = usage.get(event.requestId);
      if (receipt?.model !== model || !reserves.has(receipt.id)) throw new Error('Original holdout evidence lacks a matching reservation');
      reference.push({ prompt: event.promptSha256, case: event.id, reserved: reserves.get(receipt.id) });
    }
  }
  const cases = new Map(rows.map(row => [row.id, row]));
  const finalists = finalistSlots(audit, rows);
  const covered = new Set(reference.map(row => JSON.stringify([row.prompt, row.case])));
  for (const slot of finalists) {
    const originallyObserved = covered.has(JSON.stringify([slot.prompt, slot.case]));
    if (slot.missing === originallyObserved) throw new Error('Missing cells disagree with the original evidence');
  }
  return { prompts, cases, reference, finalists };
}

async function captureRuntime(path) {
  // Block the process's network routes before importing the actual runtime.
  const offline = () => { throw new Error('Network calls are disabled during capture'); };
  net.Socket.prototype.connect = offline;
  tls.connect = offline;
  globalThis.fetch = offline;
  process.env.OPENAI_API_KEY = 'offline-capture-only';
  const { openaiRuntime } = await import(pathToFileURL(path).href);
  return async (instructions, input) => {
    const captured = [];
    const journal = [];
    const runtime = openaiRuntime({ model, budgetMicrousd: 2_000_000, append: async event => journal.push(event),
      transport: async (url, request) => {
        captured.push({ url: String(url), body: request.body });
        return new Response(JSON.stringify({ error: { message: 'offline-capture', type: 'offline_capture' } }),
          { status: 403, headers: { 'content-type': 'application/json' } });
      } });
    try {
      await runtime.call({ role: 'candidate', instructions, input, signal: AbortSignal.timeout(5000),
        maxOutputTokens: maximumOutputTokens });
      throw new Error('SDK returned a response during offline capture');
    } catch (error) {
      if (error.status !== 403 || captured.length !== 1 || journal.length !== 2 ||
          journal[0].type !== 'provider-reservation' || journal[1].type !== 'provider-failure') throw error;
    }
    const { url, body } = captured[0];
    const request = JSON.parse(body);
    if (url !== 'https://api.openai.com/v1/responses' || request.model !== model ||
        request.max_output_tokens !== maximumOutputTokens || request.store !== false || request.reasoning?.effort !== 'low') {
      throw new Error('SDK capture differs from the verified candidate settings');
    }
    return { requestSha256: sha256(body), bodyBytes: Buffer.byteLength(body), reservationForByteCheck: journal[0].amount };
  };
}

async function main() {
  const { values } = parseArgs({ options: {
    audit: { type: 'string' }, archive: { type: 'string' }, 'source-plan': { type: 'string' },
    runtime: { type: 'string' }, execute: { type: 'string' }, out: { type: 'string' },
  } });
  for (const input of ['audit', 'archive', 'source-plan', 'runtime']) {
    if (!values[input]) throw new Error(`Supply --${input}`);
  }
  const publicAudit = json(new URL('../docs/recorded-independent-holdout-results-v1.json', import.meta.url));
  const prior = readFileSync(values.audit);
  if (sha256(prior) !== publicAudit.detailsSha256) throw new Error('The published independent holdout audit differs');
  const audit = JSON.parse(prior).tasks.outage;
  const archive = loadArchive(resolve(values.archive), values['source-plan'], audit);
  const runtimePath = resolve(values.runtime);
  const packageRoot = dirname(dirname(runtimePath));
  const sdk = ['@openai/agents', 'openai'].map(name => [name, json(join(packageRoot, 'node_modules', name, 'package.json')).version]);
  const plan = { protocol: 'cpo-recorded-outage-request-capture-v1', auditSha256: publicAudit.detailsSha256,
    sourcePlanSha256: sourcePlanDigest, runtimeSha256: sha256(readFileSync(runtimePath)),
    lockSha256: sha256(readFileSync(join(packageRoot, 'package-lock.json'))), node: process.version,
    sourceSha256: sha256(readFileSync(new URL(import.meta.url))), sdk: Object.fromEntries(sdk),
    model, maximumOutputTokens, mode: 'offline-transport-capture', finalistSlots: archive.finalists.length,
    historicalOutcomeGaps: archive.finalists.filter(row => row.missing).length };
  const planSha256 = sha256(JSON.stringify(plan));
  if (values.execute === undefined && values.out === undefined) {
    console.log(JSON.stringify({ ...plan, planSha256 }, null, 2));
    return;
  }
  if (values.execute !== planSha256 || !values.out || existsSync(values.out)) {
    throw new Error('Capture requires the current seal and a fresh output file');
  }
  const capture = await captureRuntime(runtimePath);
  const captured = new Map();
  async function get(slot) {
    const key = JSON.stringify([slot.prompt, slot.case]);
    if (!captured.has(key)) {
      const prompt = archive.prompts.get(slot.prompt);
      const row = archive.cases.get(slot.case);
      if (typeof prompt !== 'string' || !row) throw new Error('Packet refers to an unavailable archived prompt or case');
      captured.set(key, await capture(prompt, row.input));
    }
    return captured.get(key);
  }
  for (const observation of archive.reference) {
    const request = await get(observation);
    if (request.reservationForByteCheck !== observation.reserved) throw new Error('Current SDK body length differs from historical reservation evidence');
  }
  const requests = [];
  for (const slot of archive.finalists) {
    const { requestSha256, bodyBytes } = await get(slot);
    requests.push({ ...slot, requestSha256, bodyBytes });
  }
  writeFileSync(values.out, JSON.stringify({ plan, planSha256, historicalReservationsMatched: archive.reference.length,
    requests }) + '\n', { flag: 'wx' });
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) await main();
