# Order exact training proofs by estimated remaining cost

This replay keeps qualification-first CPO's validation, backup selection, and training gain threshold. The original training check alternates through seeded row pairs. The new check credits training grades already paid for and chooses which prompt to read next using estimated remaining proof cost. It estimates each prompt's rate from paid validation grades using the existing quarter-bin estimator. AIME reads have unit cost. ARC-AGI estimates a prompt's next training charge from its mean paid validation price, with a pooled fallback when a prompt has no price evidence. [Original math frontier](recorded-two-witness-math-transfer.md) · [Replay runner](../benchmarks/recorded_expected_training_order.py)

The decision rule still requires an exact training gain. The planner estimates independent replies at fixed rates and prices within each proof. It updates the exact favorable-reply count and remaining cases after each observed grade. The estimates govern lookup order. Every archived nominee, deployment, held-out grade, and non-training lookup count matched across 1,520 trials. [Full results and proof counts](recorded-expected-training-order-results-v1.json)

| Archive and starting prompts | Held-out passes | Original → ordered lookups | Historical cost saved |
| --- | ---: | ---: | ---: |
| AIME, original, four challengers | 489 | 1,159 → 1,160 | — |
| AIME, original, eight challengers | 485 | 1,607 → 1,604 | — |
| AIME, rotated, four challengers | 4,078 | 8,566 → 8,536 | — |
| AIME, rotated, eight challengers | 4,073 | 12,164 → 12,115 | — |
| ARC-AGI, original, four challengers | 1,561 | 1,820 → 1,844 | $3.76 |
| ARC-AGI, original, eight challengers | 1,578 | 2,020 → 2,041 | $4.30 |
| ARC-AGI, rotated, four challengers | 13,761 | 8,439 → 8,277 | $20.77 |
| ARC-AGI, rotated, eight challengers | 13,822 | 9,896 → 9,703 | $24.29 |

On the eight-challenger ARC-AGI rotation, training lookups fell from 1,738 to 1,545. At the new lookup budget, sequential GEPA cap 40 was the best affordable fixed setting. CPO led by 47 held-out passes, with a paired range of −6 to +101. At the historical cost budget, cap 44 remained affordable and the range was −13 to +87. Both comparisons remain inconclusive. The original ARC starts saved historical cost while using more lookups. These are archived evaluator prices and fixed-pool outcomes.

A follow-up tested checking incumbent training headroom before running validation. Both schedules preserved the deployed prompts and used at least as many lookups as this replay. [Incumbent precheck replay](recorded-incumbent-training-precheck.md)

A further replay compared the validation winner with its paid runner-up using exact training gains. It changed 12 deployments and added lookups in all eight settings. [Paired training comparison](recorded-corroborated-nomination.md)

An out-of-family fit skipped training for every validation pattern. It beat the affordable GEPA frontier on both archived ARC rotations and lost 78 passes on eight-challenger rotated AIME. [Calibrated training check](recorded-calibrated-training-route.md)

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. With DNS and socket connections blocked, 80 targeted tests and five subtests passed, including exhaustive training outcomes for a three-case panel with and without paid prefixes. Two full replays matched byte for byte. The replay reproduced the original math frontiers, public-selector parity receipt, and live-plan preview. The CLI rejected a stale seal. Storage Guard measured 4.0 GiB free. The export and publication worktree fit the standing 0.2 GiB LAB exception. The replay sent zero provider requests.

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.recorded_expected_training_order
python -B -m benchmarks.recorded_expected_training_order \
  --execute ed68c8db5557ccad0ef3c509dfcecc1b2a9b970b856323c60401ead35c199ae5 \
  --out NEW_REPORT.json
```
