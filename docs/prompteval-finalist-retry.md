# Retry a first-gain screen with a second validation miss

The first-gain screen saves lookups by certifying the earliest challenger to pass an incumbent miss. A challenger can pass that screening case and still fail to improve on the full validation panel. The screen can also overlook challengers that improve different cases. This replay measures whether one retry recovers enough holdout passes to justify its cost. [First-gain results](single-finalist.md)

The retry runs only when the first-gain screen keeps a non-perfect incumbent. It skips the first finalist if its certificate failed. It then walks the original proposal order and certifies the first challenger to pass the retry witness. The same-witness control reuses observations from the first screen. The rotated witness uses the second incumbent miss if one exists, so a challenger screened out on the first miss can still advance. A third policy limits the rotated retry to eight additional lookups. All three retain the existing cycle cap and use the same exact certificate, including critical-pass preservation. A certified challenger still faces the separately reserved qualification cases.

The comparison uses the same six existing PromptEval panels, 32 episodes per panel, four cycles, 12 validation cases, and the original 52-lookup cap. The archive check retains its priority and budget charge. Qualification uses the same eight reserved cases per cycle. The replay verifies the archived first-gain trace and requires both official GEPA control traces to stay identical.

## Results

| Policy | Final holdout passes | Paid lookups | Panels meeting both GEPA gates |
| --- | ---: | ---: | ---: |
| First-gain | 4,455 | 21,833 | 1 / 6 |
| Retry the same miss | 4,455 | 22,756 | 0 / 6 |
| Retry the next miss | 4,454 | 30,097 | 0 / 6 |
| Retry the next miss with up to eight extra lookups | 4,455 | 25,503 | 0 / 6 |
| Sequential GEPA | 4,483 | 31,157 | — |
| Batched GEPA | 4,466 | 22,028 | — |

The retry on a second miss produced 105 additional exact validation certificates and added 8,264 paid lookups relative to first-gain. Its final holdout fell by one pass in aggregate. The same-miss retry produced 17 additional certificates and redistributed two holdout passes across panels, with one gain and one loss. The eight-lookup variant produced one additional certificate and tied the first-gain holdout score on all six panels. The screen's extra certificates alone did not translate into a better accuracy and cost tradeoff.

Each panel must match or exceed each GEPA control's holdout passes at equal or lower cost, with at least 10% savings on a score tie. The episodes reuse holdout cases from the same recorded panels. Two offline runs produced byte-identical reports. [Sealed per-panel results](prompteval-finalist-retry-results-v1.json)

## Reproduce

Use pinned GEPA 0.1.4. Preview to obtain the seal, then add `--execute PLAN_SHA256 --out NEW_REPORT.json`.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.prompteval_finalist_retry
```
