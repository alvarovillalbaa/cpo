# Reorder the exact validation race without changing its winner

The earlier qualification replay left the AIME cost gate out of reach on the fixed search paths. This comparison changes the validation schedule, where CPO spends most of its reads. The newest-first policy uses the archive's recorded discovery iteration or call count. The shared-probe policy buys one validation reply per challenger on the first case the incumbent missed, then evaluates probe passes first. Both keep the seeded roster and its original score tie-break. [Previous cost result](recorded-paid-qualification-order.md) · [Replay runner](../benchmarks/recorded_validation_race_order.py)

The exact bound accounts for the remaining unread cases and keeps every protected critical reply. Because the search ceiling funds each entire validation panel, both schedules can still establish the same top-scoring prompt as the seeded race. Reordering can change which other challengers have enough paid validation evidence to serve as a backup. The replay keeps the existing training check, backup rule, and independent qualification and tracks that difference. Both native GEPA controls use the previously verified expected-cost qualification order.

| Eight-challenger rotation | Policy | Holdout passes | Paid lookups | Deployments changed versus seeded CPO |
| --- | --- | ---: | ---: | ---: |
| AIME | Seeded CPO | 4,073 | 12,164 | 0 |
| AIME | Shared probe | 4,063 | 12,270 | 4 |
| AIME | Newest first | 4,062 | 12,894 | 6 |
| ARC-AGI | Seeded CPO | 13,822 | 9,896 | 0 |
| ARC-AGI | Shared probe | 13,828 | 10,329 | 2 |
| ARC-AGI | Newest first | 13,858 | 11,549 | 5 |

Both schedules preserved the exact primary validation winner across 1,520 archived trials. On the AIME rotation with eight challengers, the shared probe changed the paid backup on 44 trials and newest-first changed it on 110. Both policies cost more and lost held-out passes. The shared probe saved 19 reads at the same aggregate score on the four-challenger AIME rotation. It still cost more than the matched batched GEPA control there.

On the eight-challenger ARC rotation, newest-first improved the score by 36 passes over seeded CPO. Its paired case sensitivity range against both GEPA controls was +15 to +126. It used 1,653 more lookups than seeded CPO and cost more than batched GEPA in both lookups and the recorded evaluator charges. Neither schedule cleared the joint gate. These experiments change which backup evidence was bought within a fixed archive. Fresh prompt quality and live provider costs remain unverified. [All settings, backup changes, and matched comparisons](recorded-validation-race-order-results-v1.json)

## Reproduce

Use Python 3.12 with the hash-pinned GEPA 0.1.4 wheel. With DNS and sockets blocked, 21 targeted tests passed and two full runs matched byte for byte. The exact-ranking tests enumerated all 512 binary matrices for both policies on a three-case pool with a protected case. The CLI rejected a stale seal and the ordered live plan reproduced. Storage Guard measured 6.0 GiB free. The 39 MiB export and publication worktree fit the standing 0.2 GiB LAB exception. The replay sent zero provider requests. [Exact ranking tests](../tests/unit/test_recorded_validation_race_order.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.recorded_validation_race_order
python -B -m benchmarks.recorded_validation_race_order \
  --execute 0d14cbe9144566f88fe3abe599b045007b2e4d0fef74175446de64ebdb988d09 \
  --out NEW_REPORT.json
```
