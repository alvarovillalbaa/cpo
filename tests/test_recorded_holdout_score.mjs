import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import test from 'node:test';
import { scoreJournal } from '../benchmarks/recorded_holdout_score.mjs';

const rows = [{ id: 'one', critical: true }, { id: 'two', critical: false }];
const directions = [{ cpo: 'a', control: 'b' }, { cpo: 'b', control: 'a' }];
const model = 'fixture-model';
const wire = records => records.map(record => JSON.stringify(record) + '\n').join('');
const grade = (output, row) => {
  const passed = output === row.id;
  return { passed, cause: passed ? null : 'value', matchedFields: Number(passed) };
};
const assistantMessage = (...content) => ({ type: 'message', role: 'assistant', content });
const outputText = text => ({ type: 'output_text', text });

function fixture() {
  const packet = { plan: { model, maximumOutputTokens: 32 }, requests: [] };
  const records = [];
  for (const [prompt, row] of [['a', rows[0]], ['b', rows[0]], ['b', rows[1]], ['a', rows[1]]]) {
    const sequence = packet.requests.length + 1;
    const request = JSON.stringify({ model, instructions: prompt, input: row.id });
    packet.requests.push({ prompt, case: row.id, requestSha256: createHash('sha256').update(request).digest('hex'),
      bodyBytes: Buffer.byteLength(request) });
    records.push({ sequence, arm: prompt, role: 'qualification', request, reservedMicrousd: 100_000 });
    records.push({ sequence, reply: { id: `resp_fixture_${sequence}`, object: 'response', model,
      status: 'completed', output: [assistantMessage(outputText(sequence === 1 ? 'wrong' : row.id))],
      usage: { input_tokens: 8, output_tokens: 4 } } });
  }
  return { packet, records, score: () => scoreJournal(packet, rows, directions, wire(records), grade) };
}

test('compares complete matched cases in both directions and counts usage from replies', () => {
  const result = fixture().score();
  assert.equal(result.status, 'complete');
  assert.equal(result.reportedModel, model);
  assert.deepEqual(result.usage, { inputTokens: 32, outputTokens: 16, capped: 0 });
  assert.deepEqual(result.comparisons, [
    { cpo: 'a', control: 'b', cpoPasses: 1, controlPasses: 2, cpoOnly: 0, controlOnly: 1, criticalLosses: ['one'] },
    { cpo: 'b', control: 'a', cpoPasses: 2, controlPasses: 1, cpoOnly: 1, controlOnly: 0, criticalLosses: [] },
  ]);
});

test('reports only observed outcomes and token counts for a journal with a pending request', () => {
  const setup = fixture();
  setup.records.splice(3);
  const result = setup.score();
  assert.equal(result.status, 'incomplete');
  assert.equal(result.requested, 2);
  assert.equal(result.replied, 1);
  assert.equal(result.outcomes.length, 1);
  assert.equal(result.comparisons, null);
  assert.deepEqual(result.usage, { inputTokens: 8, outputTokens: 4, capped: 0 });
  setup.records.splice(0);
  assert.equal(setup.score().reportedModel, null);
  assert.equal(setup.score().replied, 0);
});

test('rejects changed request bytes, swapped slots and repeated responses', () => {
  const changed = fixture();
  changed.records[0].request = changed.records[0].request.replace('"a"', '"z"');
  assert.throws(changed.score, /sealed slot at sequence 1/);
  const swapped = fixture();
  [swapped.records[0], swapped.records[2]] = [swapped.records[2], swapped.records[0]];
  assert.throws(swapped.score, /sealed slot at sequence 1/);
  const repeated = fixture();
  repeated.records[3].reply.id = repeated.records[1].reply.id;
  assert.throws(repeated.score, /reused at sequence 2/);
});

test('rejects a model change, impossible output usage, and a truncated record', () => {
  const changed = fixture();
  changed.records[3].reply.model = `${model}-different`;
  assert.throws(changed.score, /inconsistent provider model labels/);
  const usage = fixture();
  usage.records[3].reply.usage.output_tokens = 33;
  assert.throws(usage.score, /bounded measured usage/);
  assert.throws(() => scoreJournal(usage.packet, rows, directions, '{"sequence":1', grade), /incomplete record/);
  assert.throws(() => scoreJournal(usage.packet, rows, directions, 'private payload\n', grade),
    { message: 'Invalid JSON at journal line 1' });
});

test('preserves cap and refusal outcomes and concatenates assistant text parts in order', () => {
  const setup = fixture();
  const reply = setup.records[1].reply;
  reply.output = [{ type: 'reasoning' }, assistantMessage(outputText('o')), assistantMessage(outputText('ne'))];
  assert.equal(setup.score().outcomes[0].passed, true);
  reply.output.push(assistantMessage({ type: 'refusal', refusal: 'fixture' }));
  const capped = setup.records[3].reply;
  capped.status = 'incomplete';
  capped.incomplete_details = { reason: 'max_output_tokens' };
  capped.usage.output_tokens = 32;
  const result = setup.score();
  assert.equal(result.outcomes[0].cause, 'refusal');
  assert.equal(result.outcomes[1].cause, 'incomplete');
  assert.deepEqual(result.usage, { inputTokens: 32, outputTokens: 44, capped: 1 });
});
