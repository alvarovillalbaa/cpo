// Verify and score a supplied holdout journal without opening a provider client.
import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { parseArgs } from 'node:util';

const sha256 = bytes => createHash('sha256').update(bytes).digest('hex');
const originalCasesSha256 = '35b6f6930dbd660cabe5371ee7f7fdad7e348d1f1276faae91441a45899b18c5';
const verifiedJson = (path, expected, subject) => {
  const bytes = readFileSync(path);
  if (sha256(bytes) !== expected) throw new Error(`${subject} differs from the verified fingerprint`);
  return JSON.parse(bytes);
};
const nonnegative = value => Number.isSafeInteger(value) && value >= 0;
const slotKey = (prompt, row) => JSON.stringify([prompt, row]);

function parseRecords(raw) {
  if (!raw.length) return [];
  if (!raw.endsWith('\n')) throw new Error('Journal ends with an incomplete record');
  return raw.slice(0, -1).split('\n').map((line, index) => {
    let record;
    try { record = JSON.parse(line); } catch { throw new Error(`Invalid JSON at journal line ${index + 1}`); }
    if (!record || typeof record !== 'object' || Array.isArray(record)) {
      throw new Error(`Expected an object at journal line ${index + 1}`);
    }
    return record;
  });
}

function outputText(reply) {
  if (!Array.isArray(reply.output) || reply.output.some(item => !['reasoning', 'message'].includes(item?.type))) {
    throw new Error('Unexpected output for a single-turn candidate with no tools');
  }
  const messages = reply.output.filter(item => item.type === 'message');
  if (messages.some(item => item.role !== 'assistant' || !Array.isArray(item.content))) {
    throw new Error('Candidate reply contains an invalid assistant message');
  }
  const content = messages.flatMap(item => item.content);
  const last = messages.at(-1)?.content ?? [];
  if (content.some(item => !['output_text', 'refusal'].includes(item?.type))) {
    throw new Error('Candidate reply contains unsupported assistant content');
  }
  const output = content.filter(item => item.type === 'output_text');
  if (output.some(item => typeof item.text !== 'string')) throw new Error('Candidate output is missing its text');
  if (last.some(item => item.type === 'refusal') && !last.some(item => item.type === 'output_text')) return null;
  return output.map(item => item.text).join('');
}

function pairedResults(directions, cases, observations) {
  return directions.map(direction => {
    let cpoPasses = 0;
    let controlPasses = 0;
    let cpoOnly = 0;
    let controlOnly = 0;
    const criticalLosses = [];
    for (const row of cases) {
      const candidate = observations.get(slotKey(direction.cpo, row.id)).passed;
      const control = observations.get(slotKey(direction.control, row.id)).passed;
      cpoPasses += Number(candidate);
      controlPasses += Number(control);
      cpoOnly += Number(candidate && !control);
      controlOnly += Number(control && !candidate);
      if (row.critical && control && !candidate) criticalLosses.push(row.id);
    }
    return { cpo: direction.cpo, control: direction.control, cpoPasses, controlPasses, cpoOnly, controlOnly, criticalLosses };
  });
}

export function scoreJournal(packet, rows, directions, raw, grade) {
  const records = parseRecords(raw);
  const cases = new Map(rows.map(row => [row.id, row]));
  const keys = new Set(packet.requests.map(slot => slotKey(slot.prompt, slot.case)));
  const promptIds = new Set(packet.requests.map(slot => slot.prompt));
  if (cases.size !== rows.length || keys.size !== packet.requests.length || keys.size !== promptIds.size * cases.size ||
      packet.requests.some(slot => !cases.has(slot.case)) ||
      directions.some(pair => pair.cpo === pair.control || !promptIds.has(pair.cpo) || !promptIds.has(pair.control))) {
    throw new Error('Expected a unique complete finalist-by-case matrix and known comparison directions');
  }

  const observed = new Map();
  const responses = new Set();
  let reportedModel = null;
  let inputTokens = 0;
  let outputTokens = 0;
  let capped = 0;
  for (let i = 0; i < records.length; i += 2) {
    const sequence = i / 2 + 1;
    const slot = packet.requests[sequence - 1];
    const request = records[i];
    if (!slot || request.sequence !== sequence || request.arm !== slot.prompt || request.role !== 'qualification' ||
        typeof request.request !== 'string' || !nonnegative(request.reservedMicrousd) ||
        Buffer.byteLength(request.request) !== slot.bodyBytes || sha256(request.request) !== slot.requestSha256) {
      throw new Error(`Request does not match the sealed slot at sequence ${sequence}`);
    }
    const replyRecord = records[i + 1];
    if (replyRecord === undefined) break;
    const reply = replyRecord.reply;
    if (replyRecord.sequence !== sequence || !reply || reply.object !== 'response' || typeof reply.id !== 'string' ||
        !reply.id.startsWith('resp_') || responses.has(reply.id) || !['completed', 'incomplete'].includes(reply.status)) {
      throw new Error(`Response is invalid, missing terminal status, or reused at sequence ${sequence}`);
    }
    const matchesModel = reply.model === packet.plan.model || (typeof reply.model === 'string' &&
      reply.model.startsWith(packet.plan.model + '-'));
    if (!matchesModel || (reportedModel !== null && reply.model !== reportedModel)) {
      throw new Error('Journal contains inconsistent provider model labels');
    }
    reportedModel = reply.model;
    const usage = reply.usage;
    if (!usage || !nonnegative(usage.input_tokens) || !nonnegative(usage.output_tokens) ||
        usage.output_tokens > packet.plan.maximumOutputTokens) throw new Error('Response lacks bounded measured usage');
    inputTokens += usage.input_tokens;
    outputTokens += usage.output_tokens;
    responses.add(reply.id);
    const row = cases.get(slot.case);
    let outcome;
    if (reply.status === 'incomplete') {
      capped += Number(reply.incomplete_details?.reason === 'max_output_tokens');
      outcome = { passed: false, cause: 'incomplete', matchedFields: 0 };
    } else {
      const text = outputText(reply);
      outcome = text === null ? { passed: false, cause: 'refusal', matchedFields: 0 } : grade(text, row);
    }
    observed.set(slotKey(slot.prompt, slot.case), { prompt: slot.prompt, case: slot.case, ...outcome });
  }
  const complete = observed.size === packet.requests.length;
  return {
    status: complete ? 'complete' : 'incomplete', requested: Math.ceil(records.length / 2), replied: observed.size,
    planned: packet.requests.length, reportedModel,
    usage: { inputTokens, outputTokens, capped }, outcomes: [...observed.values()],
    comparisons: complete ? pairedResults(directions, rows, observed) : null,
  };
}

async function main() {
  const options = Object.fromEntries(['packet', 'audit', 'cases', 'grader', 'wire', 'out'].map(key => [key, { type: 'string' }]));
  const { values } = parseArgs({ options });
  for (const key of Object.keys(options)) if (!values[key]) throw new Error(`Supply --${key}`);
  const publicPacket = JSON.parse(readFileSync(new URL('../docs/recorded-holdout-request-packet-v1.json', import.meta.url)));
  const publicAudit = JSON.parse(readFileSync(new URL('../docs/recorded-independent-holdout-results-v1.json', import.meta.url)));
  const packet = verifiedJson(values.packet, publicPacket.detailsSha256, 'Holdout request packet');
  const audit = verifiedJson(values.audit, publicAudit.detailsSha256, 'Independent holdout audit');
  const source = verifiedJson(values.cases, originalCasesSha256, 'Original outage plan');
  if (sha256(readFileSync(values.grader)) !== publicAudit.plan.sourceGraderSha256) throw new Error('Original grader differs');
  const { gradeStructuredFields } = await import(pathToFileURL(resolve(values.grader)).href);
  const wire = readFileSync(values.wire);
  const raw = new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(wire);
  const report = scoreJournal(packet, source.datasets.holdout, audit.tasks.outage.distinctDirections, raw, gradeStructuredFields);
  writeFileSync(values.out, JSON.stringify({ protocol: 'cpo-recorded-outage-journal-score-v1',
    packetSha256: publicPacket.detailsSha256, wireSha256: sha256(wire), ...report }) + '\n', { flag: 'wx' });
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) await main();
