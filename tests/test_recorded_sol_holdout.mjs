import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import test from 'node:test';

import { scorePanel } from '../benchmarks/recorded_sol_holdout.mjs';

const cases = [{ id: 'protected', critical: true }, { id: 'ordinary', critical: false }];
const model = 'fixture';
const grade = (text, row) => ({ passed: text === row.id, matchedFields: Number(text === row.id) });
const wire = records => records.map(record => JSON.stringify(record) + '\n').join('');

function fixture(scope) {
  const requests = [];
  const records = [];
  for (const row of cases) {
    for (const prompt of ['a', 'b']) {
      const request = JSON.stringify({ prompt, case: row.id });
      const slot = { prompt, case: row.id, missing: prompt === 'b', bodyBytes: Buffer.byteLength(request),
        reservedMicrousd: 100_000, requestSha256: createHash('sha256').update(request).digest('hex') };
      requests.push(slot);
      if (scope === 'missing' && !slot.missing) continue;
      const sequence = records.length / 2 + 1;
      records.push({ sequence, arm: prompt, role: 'qualification', request, reservedMicrousd: slot.reservedMicrousd });
      const passed = prompt === 'b' || !row.critical;
      records.push({ sequence, reply: { id: `resp_fixture_${sequence}`, object: 'response', model,
        status: 'completed', usage: { input_tokens: 8, output_tokens: 2 },
        output: [{ type: 'message', role: 'assistant', content: [{ type: 'output_text', text: passed ? row.id : 'wrong' }] }] } });
    }
  }
  const direction = { cpo: 'a', control: 'b' };
  const packet = { plan: { model, maximumOutputTokens: 16 }, requests, distinctDirections: [direction],
    groups: [{ evaluationQuotes: 60, controlArm: 'native', samePromptPaths: 2, pairs: [{ ...direction, weight: 3 }] }] };
  return { records, run: () => scorePanel(packet, cases, scope, wire(records), grade) };
}

test('weights reused prompt pairs only after a complete matched journal', () => {
  const panel = fixture('matched');
  assert.deepEqual(panel.run().weightedGroups, [{ evaluationQuotes: 60, controlArm: 'native', samePromptPaths: 2,
    passDifference: -3, criticalLosses: 3 }]);
  panel.records.pop();
  assert.equal(panel.run().status, 'incomplete');
  assert.equal(panel.run().weightedGroups, null);
});

test('keeps missing-only scores separate from matched comparisons', () => {
  const result = fixture('missing').run();
  assert.equal(result.status, 'complete');
  assert.equal(result.replied, 2);
  assert.equal(result.comparisons, null);
  assert.equal(result.weightedGroups, null);
});

test('rejects changed reservation and input usage beyond the quote', () => {
  const a = fixture('matched');
  a.records[0].reservedMicrousd -= 1;
  assert.throws(a.run, /Sol quote/);
  const b = fixture('matched');
  b.records[1].reply.usage.input_tokens = Buffer.byteLength(b.records[0].request) + 2049;
  assert.throws(b.run, /Sol quote/);
});
