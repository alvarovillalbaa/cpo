# Give fresh search priority over archive retries

The cached-witness replay lost 25 holdout passes on one Flan-T5-XXL ends-with-word episode. In cycle three, a cached witness surfaced prompt 66. It passed validation and failed qualification. The next cycle's archive check promoted it and skipped fresh search. The seeded screen had instead reached prompt 61 in cycle four. This replay tests whether changing archive priority recovers the loss while preserving the episode budget. [Cached-witness replay](cached-miss-witness.md)

The preflight control keeps the original archive priority. Fresh-first gives the original fresh pool its full search allowance and independent qualification first. If no fresh prompt promotes, the most recent eligible archive prompt may use the unused part of the original combined search and qualification ceiling. A retry reuses any incumbent replies from fresh qualification on those same cases. It still needs a strict gain and can spend only what is left. Each incumbent and archive prompt can be compared once in that direction.

Both orderings run with the seeded witness and the cached witness that requires two prior passes. The runner verifies both preflight arms against their published callback traces, scores, and costs. All four arms share the original pools, schedules, independent qualification cases, and final holdout. GEPA comparisons use the published sequential and batched controls that reinvest cache hits within the paid cap. [Runner](../benchmarks/archive_after_fresh_search.py) · [GEPA controls](gepa-paid-cap-transfer.md)

## Results

| Witness and archive order | Holdout passes | Paid lookups | Archive promotions | Panels clearing both GEPA gates / 32 |
| --- | ---: | ---: | ---: | ---: |
| Seeded, preflight | 21,023 | 101,034 | 327 | 15 |
| Seeded, fresh-first | 21,049 | 106,572 | 262 | 13 |
| Cached, preflight | 21,006 | 100,931 | 329 | 17 |
| Cached, fresh-first | 21,046 | 106,571 | 265 | 16 |

Fresh-first gained 26 passes and spent 5,538 more lookups with the seeded witness. It gained 40 passes and spent 5,640 more lookups with the cached witness. Each fresh-first arm cleared both GEPA gates on fewer panels than its preflight control. Neither arm exhausted the combined ceiling before starting an eligible fallback. The seeded preflight configuration remains the default.

On ends-with-word seed 47690, the seeded arms both selected prompt 61 and scored 30 of 30. Cached preflight selected the archived prompt 66 and scored 5 of 30. Cached fresh-first selected a different fresh prompt, 6, and scored 4 of 30. Giving fresh search priority removed the archive preemption in that episode. The cached witness still changed the final search enough to miss prompt 61.

All three phases reproduced byte for byte offline across 1,024 paired episodes per arm. These fixed prompt-pool results establish the effect of ordering on the archived trajectories. Fresh-model performance and provider costs remain unverified. [Sealed results and incident trace](archive-after-fresh-search-results-v1.json)

## Reproduce

Use GEPA 0.1.4. Preview the phase seal, then pass `--execute PLAN_SHA256 --out NEW_REPORT.json`. Phases are `mmlu`, `bbh-lmentry`, and `bbh-lmentry-stress`.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.archive_after_fresh_search --phase bbh-lmentry-stress
```
