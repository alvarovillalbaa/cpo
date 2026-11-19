# Give candidates a second validation probe within the search cap

On the eight new MMLU panels, CPO missed batched GEPA's winner in 12 losing episodes even though the archived outcomes would have cleared both strict CPO gates on its offered cycle. This experiment compares broader screens and checks those 12 episodes after ranking. The loss labels are used only for reporting. [Loss attribution](starting-prompt-margin.md)

Both second-probe variants measure the incumbent, then probe candidates on its first validation miss in the original proposal order. They use spare search allowance for a second shared probe on the next incumbent miss, or an incumbent pass if there is only one miss. One variant gives second probes first to candidates that passed the first probe. The other gives first priority to candidates that failed. Ties retain the original proposal order.

The screen reserves enough lookups to finish one certificate. Candidates must pass at least one probed incumbent miss to reach a shortlist of two. The shortlist orders measured pass rates after adding one pass and one failure. Each attempted certificate needs enough remaining budget to finish and uses the existing strict-gain and critical-pass rules. Certified halving uses the existing CPO library selector. All arms share the original proposal blocks, recency archive, 52-lookup search ceiling, and the independent qualification gate. [Runner](../benchmarks/budgeted_second_probe.py) · [Certified halving](certified-pool.md)

## Results

| Screen | New MMLU passes / paid lookups | Earlier cohorts passes / paid lookups | Panels clearing both GEPA gates / 40 |
| --- | ---: | ---: | ---: |
| Seeded deferred first-gain | 8,971 / 21,477 | 21,023 / 101,034 | 17 |
| Certified halving | 9,005 / 46,404 | 20,495 / 172,261 | 0 |
| Second probe prioritizes first passes | 9,008 / 44,383 | 21,273 / 178,278 | 0 |
| Second probe prioritizes first failures | 9,009 / 44,447 | 21,261 / 178,734 | 0 |

Batched GEPA scored 8,996 at 29,285 paid lookups on the new panels. Prioritizing first failures gained 13 passes and used 15,162 more lookups. Both second-probe variants improved aggregate accuracy over the seeded screen on the new and earlier cohorts. No broader screen cleared both GEPA gates on any panel. Seeded deferred first-gain remains the default.

Certified halving brought the exact batched GEPA winner to qualification in five of the 12 audited losses and matched or exceeded GEPA's holdout score in six. Each second-probe variant brought one such winner to qualification and matched GEPA in one audited loss. Their aggregate gains therefore come mostly from other episodes. The full results preserve episode-level comparisons and callback trace hashes. [Sealed results](budgeted-second-probe-results-v1.json)

All four phases replayed twice offline with byte-identical results. The seeded control reproduced its published trace, score, and costs on all 40 panels. Exhaustive checks on 4,096 combinations of binary outcomes, budgets, and probe orders verified strict gain, critical-pass protection, and lookup accounting. These experiments evaluate recorded prompt pools. Fresh-model superiority and provider costs remain unverified.

## Reproduce

Use GEPA 0.1.4. Preview the phase seal, then add `--execute PLAN_SHA256 --out NEW_REPORT.json`. Phases are `independent`, `mmlu`, `bbh-lmentry`, and `bbh-lmentry-stress`.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.budgeted_second_probe --phase independent
```
