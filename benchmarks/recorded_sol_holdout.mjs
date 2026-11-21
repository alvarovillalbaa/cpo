// Capture the Sol outage requests through an offline SDK stub and score supplied replies.
import { createHash } from 'node:crypto';
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import net from 'node:net';
import { dirname, join, resolve } from 'node:path';
import tls from 'node:tls';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { parseArgs } from 'node:util';

import { finalistSlots } from './recorded_holdout_requests.mjs';
import { scoreJournal } from './recorded_holdout_score.mjs';

const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const model = 'gpt-6.2-sol';
const maximumOutputTokens = 384;
const designSha256 = '5b938f0eb190cdca197c1e050bf78835e84f023d2feea1e481d4796ccfcbf236';
const sourcePlanSha256 = '4023fb794d1488f61a6518e28214423ed904b0f68b6ca67ea524af01aa3a3f84';
const graderSha256 = '63b2b23fbb4b229729fa3e5ddc79590242b0d864ce4c56adc6a462e89c57ca58';
const casePlanSha256 = '35b6f6930dbd660cabe5371ee7f7fdad7e348d1f1276faae91441a45899b18c5';
const runtimeSha256 = '270ff6649d255ba91c96c2b12f87e7ddd73e71acdbc83d5fe425bf674ca0cc45';
const lockSha256 = '94acfff055b81a482684cd4cb17aef8de5e84d049575b991f81c48bf3d71ee05';
const pairKey = (a, b) => JSON.stringify([a, b]);
const save = (path, value) => writeFileSync(path, JSON.stringify(value, null, 2) + '\n', { flag: 'wx' });

function verifiedBytes(path, fingerprint) {
  const raw = readFileSync(path);
  if (sha(raw) !== fingerprint) throw new Error('A sealed Sol source differs from its fingerprint');
  return raw;
}

function loadArchive(root, sourcePlan, design) {
  const source = JSON.parse(verifiedBytes(sourcePlan, sourcePlanSha256)).taskSources.outage;
  for (const [file, fingerprint] of Object.entries(source)) verifiedBytes(join(root, file), fingerprint);

  const cases = JSON.parse(verifiedBytes(join(root, 'outage-strict-plan.json'), casePlanSha256)).datasets.holdout;
  const prompts = new Map();
  const observed = [];
  for (const policy of ['strict', 'fields', 'hybrid']) {
    const plan = JSON.parse(readFileSync(join(root, `outage-${policy}-plan.json`)));
    if (plan.model !== model || plan.tokenCaps.candidate !== maximumOutputTokens ||
        JSON.stringify(plan.datasets.holdout) !== JSON.stringify(cases)) {
      throw new Error('Historical Sol model settings or case rows differ');
    }
    const directory = join(root, `outage-${policy}`);
    const result = JSON.parse(readFileSync(join(directory, 'results.json')));
    const entries = [result.holdoutBaseline, result.holdoutCandidate, ...result.rounds.flatMap(round => round.arms)];
    for (const { prompt, promptSha256 } of entries) {
      if (sha(JSON.stringify(prompt)) !== promptSha256) throw new Error('Archived instructions differ');
      prompts.set(promptSha256, prompt);
    }
    const events = readFileSync(join(directory, 'events.jsonl'), 'utf8').trim().split('\n').map(line => JSON.parse(line));
    const usage = new Map(events.filter(row => row.type === 'provider-usage').map(row => [row.responseId, row]));
    const reserved = new Map(events.filter(row => row.type === 'provider-reservation').map(row => [row.id, row.amount]));
    for (const row of events.filter(row => row.type === 'evaluation' && row.split === 'holdout')) {
      const receipt = usage.get(row.requestId);
      if (receipt?.model !== model || !reserved.has(receipt.id)) throw new Error('Historical holdout charge is unpaired');
      observed.push({ prompt: row.promptSha256, case: row.id, reserved: reserved.get(receipt.id) });
    }
  }
  const distinctDirections = [...new Map(design.groups.flatMap(group => group.pairs).map(pair =>
    [pairKey(pair.cpo, pair.control), { cpo: pair.cpo, control: pair.control }])).values()];
  const slots = finalistSlots({ distinctDirections, missingPromptCases: design.missingPromptCases }, cases);
  const covered = new Set(observed.map(row => pairKey(row.prompt, row.case)));
  for (const slot of slots) {
    if (typeof prompts.get(slot.prompt) !== 'string' || slot.missing === covered.has(pairKey(slot.prompt, slot.case))) {
      throw new Error('A new Sol slot disagrees with archived prompts or holdout coverage');
    }
  }
  return { cases: new Map(cases.map(row => [row.id, row])), prompts, observed, slots, distinctDirections };
}

export async function offlineCapture(runtimePath) {
  const deny = () => { throw new Error('Real network calls are disabled during Sol request capture'); };
  net.Socket.prototype.connect = deny;
  tls.connect = deny;
  globalThis.fetch = deny;
  process.env.OPENAI_API_KEY = 'offline-capture-only';
  const { openaiRuntime } = await import(pathToFileURL(runtimePath).href);
  return async (instructions, input) => {
    const events = [];
    const requests = [];
    const runtime = openaiRuntime({ model, budgetMicrousd: 2_000_000, append: async event => events.push(event),
      transport: async (url, init) => {
        requests.push({ url: String(url), body: init.body });
        return new Response('{"error":{"message":"offline Sol capture","type":"offline_capture"}}',
          { status: 403, headers: { 'content-type': 'application/json' } });
      } });
    try {
      await runtime.call({ role: 'candidate', instructions, input, maxOutputTokens: maximumOutputTokens,
        signal: AbortSignal.timeout(5_000) });
      throw new Error('Offline Sol capture unexpectedly received a response');
    } catch (error) {
      if (error.status !== 403 || requests.length !== 1 || events.length !== 2 ||
          events[0].type !== 'provider-reservation' || events[1].type !== 'provider-failure') throw error;
    }
    const { url, body } = requests[0];
    const request = JSON.parse(body);
    const bodyBytes = Buffer.byteLength(body);
    const reservedMicrousd = 24 * (bodyBytes + 2048) + 120 * maximumOutputTokens;
    if (url !== 'https://api.openai.com/v1/responses' || request.model !== model || request.store !== false ||
        request.max_output_tokens !== maximumOutputTokens || request.reasoning?.effort !== 'low' ||
        request.reasoning.summary !== undefined || request.include?.some(field => field.startsWith('reasoning.')) ||
        events[0].amount !== reservedMicrousd) {
      throw new Error('Archived Sol serialization or reservation formula differs');
    }
    return { body, bodyBytes, reservedMicrousd, requestSha256: sha(body) };
  };
}

async function capture(values) {
  const design = JSON.parse(verifiedBytes(values.design, designSha256));
  const archive = loadArchive(resolve(values.archive), values['source-plan'], design);
  const runtimePath = resolve(values.runtime);
  const packageRoot = dirname(dirname(runtimePath));
  verifiedBytes(runtimePath, runtimeSha256);
  verifiedBytes(join(packageRoot, 'package-lock.json'), lockSha256);
  const sdk = Object.fromEntries(['@openai/agents', 'openai'].map(name => [name,
    JSON.parse(readFileSync(join(packageRoot, 'node_modules', name, 'package.json'))).version]));
  if (sdk['@openai/agents'] !== '0.22.0' || sdk.openai !== '7.58.0') throw new Error('The archived SDK versions differ');
  const plan = { protocol: 'cpo-sol-outage-request-capture-v1', designSha256, sourcePlanSha256, casePlanSha256,
    graderSha256, runtimeSha256, lockSha256, node: process.version, sdk, model, maximumOutputTokens,
    sourceSha256: sha(readFileSync(new URL(import.meta.url))), mode: 'offline-capture',
    matchedRequests: archive.slots.length, missingRequests: archive.slots.filter(slot => slot.missing).length };
  const planSha256 = sha(JSON.stringify(plan));
  if (values.execute === undefined && values.out === undefined) {
    console.log(JSON.stringify({ ...plan, planSha256 }, null, 2));
    return;
  }
  if (values.execute !== planSha256 || !values.out || existsSync(values.out)) throw new Error('Use the current seal and a fresh output path');
  const captureRequest = await offlineCapture(runtimePath);
  const cached = new Map();
  async function captureSlot(slot) {
    const key = pairKey(slot.prompt, slot.case);
    if (!cached.has(key)) {
      const { bodyBytes, requestSha256, reservedMicrousd } = await captureRequest(
        archive.prompts.get(slot.prompt), archive.cases.get(slot.case).input);
      cached.set(key, { bodyBytes, requestSha256, reservedMicrousd });
    }
    return cached.get(key);
  }
  for (const row of archive.observed) {
    if ((await captureSlot(row)).reservedMicrousd !== row.reserved) throw new Error('Historical reservation length check failed');
  }
  const requests = [];
  for (const slot of archive.slots) requests.push({ ...slot, ...await captureSlot(slot) });
  const reserve = rows => rows.reduce((sum, row) => sum + row.reservedMicrousd, 0);
  save(values.out, { plan, planSha256, historicalReservationsMatched: archive.observed.length,
    matchedReservationMicrousd: reserve(requests), missingReservationMicrousd: reserve(requests.filter(row => row.missing)),
    groups: design.groups, distinctDirections: archive.distinctDirections, requests });
}

export function scorePanel(packet, cases, scope, raw, grade) {
  if (!['matched', 'missing'].includes(scope)) throw new Error('Select matched or missing scope');
  const full = scope === 'matched';
  const requests = full ? packet.requests : packet.requests.filter(row => row.missing);
  const selected = { ...packet, requests };
  const result = scoreJournal(selected, cases, full ? packet.distinctDirections : [], raw, grade);
  const records = raw ? raw.slice(0, -1).split('\n') : [];
  for (let i = 0; i < records.length; i += 2) {
    const request = JSON.parse(records[i]);
    const slot = requests[i / 2];
    const usage = i + 1 < records.length ? JSON.parse(records[i + 1]).reply.usage : null;
    if (request.reservedMicrousd !== slot.reservedMicrousd || (usage && usage.input_tokens > slot.bodyBytes + 2048)) {
      throw new Error('Journal reservation or reported usage differs from the Sol quote');
    }
  }
  const comparisons = new Map(result.comparisons?.map(row => [pairKey(row.cpo, row.control), row]));
  const weightedGroups = full && result.status === 'complete' ? packet.groups.map(group => {
    let passDifference = 0;
    let criticalLosses = 0;
    for (const { cpo, control, weight } of group.pairs) {
      const row = comparisons.get(pairKey(cpo, control));
      passDifference += weight * (row.cpoPasses - row.controlPasses);
      criticalLosses += weight * row.criticalLosses.length;
    }
    return { evaluationQuotes: group.evaluationQuotes, controlArm: group.controlArm,
      samePromptPaths: group.samePromptPaths, passDifference, criticalLosses };
  }) : null;
  return { ...result, comparisons: full ? result.comparisons : null, weightedGroups };
}

async function score(values) {
  const receipt = JSON.parse(readFileSync(new URL('../docs/recorded-sol-provider-holdout-receipt-v1.json', import.meta.url)));
  const packet = JSON.parse(verifiedBytes(values.packet, receipt.packetSha256));
  const cases = JSON.parse(verifiedBytes(values.cases, casePlanSha256)).datasets.holdout;
  verifiedBytes(values.grader, graderSha256);
  const { gradeStructuredFields } = await import(pathToFileURL(resolve(values.grader)).href);
  const wire = readFileSync(values.wire);
  const raw = new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(wire);
  const result = scorePanel(packet, cases, values.scope, raw, gradeStructuredFields);
  save(values.out, { protocol: 'cpo-sol-outage-panel-score-v1', scope: values.scope,
    packetSha256: receipt.packetSha256, wireSha256: sha(wire), ...result });
}

async function main() {
  const [mode, ...args] = process.argv.slice(2);
  const required = mode === 'capture' ? ['design', 'archive', 'source-plan', 'runtime'] :
    mode === 'score' ? ['packet', 'scope', 'cases', 'grader', 'wire', 'out'] : null;
  if (!required) throw new Error('Specify capture or score');
  const keys = mode === 'capture' ? [...required, 'execute', 'out'] : required;
  const { values } = parseArgs({ args, options: Object.fromEntries(keys.map(key => [key, { type: 'string' }])) });
  for (const key of required) if (!values[key]) throw new Error(`Supply --${key}`);
  await (mode === 'capture' ? capture(values) : score(values));
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) await main();
