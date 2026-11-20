# Veto one-pass promotions when fresh cases show a loss

Requiring a second gain rejected most one-pass promotions. The narrower rule rejects a one-pass promotion only if the challenger loses on the two reserved cases. A tie leaves the original promotion in effect. The search, case reserve, margin proof, and accounting stay the same. The audit arm buys the additional evidence and always keeps the original decision. [Earlier corroboration replay](proposal-qualification-corroboration.md) · [Runner](../benchmarks/proposal_qualification_veto.py)

The primary comparison uses eight additional archived panels. College biology, machine learning, nutrition, and security studies each have a Gemma 7B IT and a Falcon 40B panel. The subjects and models are disjoint from both earlier proposal replay cohorts. This run applies the proposal replay’s schedules and budgets, including cap-72 CPO, to the archived matrices and their published holdout splits. [Archive provenance](independent-mmlu-transfer.md) · [Archived correctness tables](../benchmarks/data/independent-mmlu-transfer-v1.json)

The gate requires the joint paired 95% range against both official GEPA modes to be above zero and total paid lookups to be at or below both controls. Each archive case can enter the reserve only if every search and qualification stage in the episode leaves it unused. A full two-case reserve was available in 614 of 1,024 cycles on the additional panels. The machine learning panels had no reserve.

## Results

| Policy | Development passes / lookups | Earlier transfer passes / lookups | Additional archive passes / lookups |
| --- | ---: | ---: | ---: |
| Original cap-72 CPO | 4,159 / 33,177 | 10,237 / 66,831 | 9,000 / 66,958 |
| Veto only on loss | 4,159 / 33,541 | 10,240 / 67,259 | 9,004 / 67,222 |
| Require corroboration | 4,147 / 33,667 | 10,245 / 67,522 | 8,964 / 67,284 |
| Audit without veto | 4,159 / 33,534 | 10,237 / 67,264 | 9,000 / 67,282 |
| Sequential GEPA | 4,139 / 44,944 | 10,236 / 91,649 | 9,012 / 92,773 |
| Batched GEPA | 4,176 / 44,194 | 10,263 / 88,226 | 9,020 / 89,426 |

On the additional panels, the veto arm reviewed 61 one-pass promotions. The extra cases tied on 53, favored the challenger on two, and favored the incumbent on six. The veto arm gained four passes over cap-72 CPO and used 264 more lookups. It saved 22,204 lookups against batched GEPA and finished 16 passes behind it. The joint range against both GEPA controls was −72 to +26 passes. The rule failed the primary gate, so the original promotion rule remains the default. [Panel counts, scores, and intervals](proposal-qualification-veto-results-v1.json)

The follow-up moved the budget change to search, with short screening and full validation of the chosen challenger. [Short validation replay](proposal-short-validation.md)

## Reproduce offline

Use pinned GEPA 0.1.4 and a fresh output path.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.proposal_qualification_veto
PYTHONHASHSEED=0 python -B -m benchmarks.proposal_qualification_veto \
  --execute 9dffee272a0b6f0cba95528ea08dd980855e2ff3e862e9d1cf8ea224e8a0650b \
  --out NEW_REPORT.json
```

Two clean source replays blocked sockets and DNS and matched byte for byte. Each exercised 7,680 experimental cycles, reproduced 72 published panel traces, and separately repeated 16 official GEPA paths on the additional archive. Six focused tests passed, including all extra-panel win, tie, and loss combinations. The CLI rejected a stale seal and preserved an existing report. Storage Guard measured 10.7 GiB free. The 26.7 MB scratch export was removed under the standing LAB exception. [Tests](../tests/unit/test_proposal_qualification_veto.py) · [Verification receipt](proposal-qualification-veto-verification-v1.json) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
