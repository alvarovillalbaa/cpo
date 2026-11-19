# Spend the wider validation screen once

Using two validation probes on most fresh candidates improved aggregate holdout accuracy and used more paid lookups than the GEPA controls. This replay asks whether one wider cycle can retain enough of that gain. It uses the published screen that prioritizes first-probe failures for a second observation. [Two-probe results](budgeted-second-probe.md)

Four schedules run the wider screen at most once per four-cycle episode. **First cycle** and **final cycle** use fixed positions. **Late at start** uses the first available fresh search in cycles three or four while the starting prompt is incumbent. **Final with credit** widens in cycle four only if prior distinct paid search lookups plus the entire remaining cycle search cap fit within 96. The credit uses search calls. Qualification is charged separately in the final totals. If the archive promotes first, that cycle has no fresh search. An episode can therefore use zero wide cycles.

The seeded-only and wide-all controls reproduce their published callback traces, scores, and costs. Every arm uses the same proposal blocks, recency archive, qualification panel, and original per-cycle cap. Widening checks use only the cycle position, incumbent identity, and actual prior search charges. The 96-credit rule verifies the search ceiling on every episode where it widens. [Runner](../benchmarks/single_wide_cycle.py)

## Results

| Schedule | New MMLU passes / paid lookups | Earlier cohorts passes / paid lookups | Episodes widened / 1,280 | Both GEPA gates / 40 |
| --- | ---: | ---: | ---: | ---: |
| Seeded only | 8,971 / 21,477 | 21,023 / 101,034 | 0 | 17 |
| Wide on every fresh search | 9,009 / 44,447 | 21,261 / 178,734 | 1,280 | 0 |
| First cycle | 8,984 / 28,012 | 21,124 / 124,507 | 1,280 | 7 |
| Final cycle | 8,975 / 27,244 | 21,058 / 120,288 | 1,149 | 13 |
| Late at start | 8,980 / 26,730 | 21,071 / 114,754 | 818 | 19 |
| Final with credit | 8,978 / 23,868 | 21,036 / 106,432 | 359 | 17 |

Late-at-start cleared both GEPA gates on four of the eight newer MMLU panels, up from two for seeded CPO. It improved the seeded aggregate by nine passes on those panels and used 5,253 additional lookups. Batched GEPA still scored 16 more passes at a cost of 2,555 more lookups. The credit rule saved 5,417 lookups against batched GEPA and finished 18 passes behind. Its additional search matched GEPA's score in two of the 12 previously audited strict-gain losses.

The first-cycle rule produced the highest aggregate accuracy among the single-cycle rules. It cleared both GEPA gates on seven panels. The late-at-start rule had the widest panel-level success at 19, while the always-wide rule produced the highest aggregate pass totals. The seeded screen remains the default.

All four phases replayed byte for byte offline. The results cover 1,280 episodes per method and reproduce both static controls on all 40 panels. These experiments measure fixed archived prompt pools. Fresh-model superiority and provider costs remain unverified. [Sealed results](single-wide-cycle-results-v1.json)

## Reproduce

Use GEPA 0.1.4. Preview the phase seal, then add `--execute PLAN_SHA256 --out NEW_REPORT.json`. Phases are `independent`, `mmlu`, `bbh-lmentry`, and `bbh-lmentry-stress`.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.single_wide_cycle --phase independent
```
