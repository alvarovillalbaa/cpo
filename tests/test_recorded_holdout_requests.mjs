import assert from 'node:assert/strict';
import { test } from 'node:test';
import { finalistSlots } from '../benchmarks/recorded_holdout_requests.mjs';

test('each finalist shares every holdout case and reversals do not duplicate slots', () => {
  const audit = { distinctDirections: [{ cpo: 'A', control: 'B' }, { cpo: 'B', control: 'A' }],
    missingPromptCases: { B: ['first', 'second'] } };
  assert.deepEqual(finalistSlots(audit, [{ id: 'second' }, { id: 'first' }]), [
    { prompt: 'A', case: 'first', missing: false },
    { prompt: 'B', case: 'first', missing: true },
    { prompt: 'B', case: 'second', missing: true },
    { prompt: 'A', case: 'second', missing: false },
  ]);
});

test('a gap cannot introduce an unrelated prompt or a development case', () => {
  const distinctDirections = [{ cpo: 'A', control: 'B' }];
  const cases = [{ id: 'original-holdout' }];
  assert.throws(() => finalistSlots({ distinctDirections, missingPromptCases: { C: ['original-holdout'] } }, cases),
    /must name a finalist/);
  assert.throws(() => finalistSlots({ distinctDirections, missingPromptCases: { B: ['development'] } }, cases),
    /unique holdout cases/);
});
