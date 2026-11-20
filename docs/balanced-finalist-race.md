# Compare two finalists on matched validation cases

The BBH and LMentry tie-extension trial left a gap against both original GEPA modes even with eight-case CPO. This follow-up replays the original eight-case CPO and both official GEPA 0.1.4 arms. In 110 of 247 losing comparisons, the final GEPA prompt would have passed CPO's strict validation and qualification gates when it was offered. Counting the controls separately, those comparisons account for 526 gross lost holdout passes before offsetting wins. They identify cases where a search change could have helped on the measured trajectory. [Cross-benchmark trial](tie-extension-cross-benchmark.md) · [Per-episode loss audit](balanced-finalist-race-results-v1.json)

## Search policies

The two balanced races fully score the incumbent. They then screen either the first four challengers on four shared cases or the first six on two cases. The screen uses equal numbers of incumbent passes and misses where possible. The best two challengers on that screen advance in score order. Each has enough budget to complete a full validation challenge under the original cap, even after the maximum archive debit. Exact racing can reject a challenger early when it can no longer beat the leader. The shared results are charged once, and a candidate cannot replace the incumbent without an exact validation gain and usual independent qualification. [Fixed-pool selector](../cpo/pool.py) · [Benchmark implementation](../benchmarks/balanced_finalist_race.py)

Two routed policies use the six-candidate race only when the starting prompt is still incumbent or when the incumbent fails its first two scheduled validation cases. In other cycles they use the original deferred first-gain search. The routing probes count toward the cycle cap, and any overlap with the chosen race is reused. Controls include ordinary proposal-order exact racing, certified halving, and rechecking candidates that fail a first miss probe. All policies use the original eight-case qualification, recency archive, and 52-lookup search ceiling. [Earlier second-probe study](budgeted-second-probe.md) · [Shortlist and budget tests](../tests/unit/test_balanced_finalist_race.py)

## Results

Each cell gives final holdout passes and paid lookups. Both cohorts were available before this study.

| Method | BBH and LMentry | MMLU |
| --- | ---: | ---: |
| Seeded first-gain CPO | 3,304 / 34,647 | 22,334 / 29,572 |
| Certified halving | 3,341 / 64,111 | 22,450 / 67,294 |
| Recheck first failures | 3,483 / 64,954 | 22,441 / 59,848 |
| Proposal-order exact race | 3,380 / 69,263 | 22,467 / 65,592 |
| Balanced four-candidate race | 3,462 / 67,131 | 22,453 / 59,079 |
| Balanced six-candidate race | 3,467 / 66,768 | 22,464 / 56,591 |
| Widen when the starting prompt is incumbent | 3,410 / 57,946 | 22,441 / 54,310 |
| Widen after two incumbent misses | 3,429 / 55,332 | 22,390 / 37,902 |
| Batched GEPA | 3,396 / 47,537 | 22,352 / 38,990 |
| Sequential GEPA | 3,457 / 65,252 | 22,361 / 56,504 |

The six-candidate race brought the final score to at least GEPA's score in 61 of the 110 audited BBH and LMentry losses. Rechecking first failures matched or exceeded GEPA in 31 of those comparisons and produced the highest overall CPO score on that cohort. It gained 26 passes and used 298 fewer lookups than sequential GEPA, while using 17,417 more lookups than batched GEPA. The result keeps the lookup cost of the stronger search visible alongside its accuracy.

Widening after two misses triggered in 761 of the 1,536 scheduled BBH and LMentry cycles and 311 of 1,536 MMLU cycles. It gained **38 passes and saved 1,088 lookups** against batched GEPA on MMLU. It gained **29 passes and saved 18,602 lookups** against sequential GEPA. The MMLU accuracy difference remains nonnegative against both controls after omitting any one subject. Removing professional law leaves an eight-pass lead over batched GEPA and a tie with sequential GEPA. On BBH and LMentry the same policy gained 33 passes and paid 7,795 more lookups than batched GEPA, and scored 28 fewer passes than sequential GEPA. The routing decision was tested after observing these archives. The default stays at seeded first-gain. [Sealed results](balanced-finalist-race-results-v1.json)

The prospective transfer to two unused MMLU model splits gained 58 passes over seeded CPO and failed the frozen gate against both GEPA controls. [Model-split transfer](routed-finalist-model-transfer.md)

## Reproduce

Use pinned GEPA 0.1.4. The other phase is `mmlu`. Preview its separate seal before executing.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.balanced_finalist_race --phase bbh-lmentry
PYTHONHASHSEED=0 python -B -m benchmarks.balanced_finalist_race \
  --phase bbh-lmentry --execute af5a7ac6f4686b74be2f6334badfa9001d4a8a0089262303310ec5ce8436efdd \
  --out NEW_REPORT.json
```

Two offline runs per cohort matched byte for byte. All 24 seeded CPO traces and 48 original GEPA panel traces reproduced. Both focused tests passed, and the CLI rejected a stale seal. Storage Guard measured 14.8 GiB free. The standing LAB exception covered the 11.4 MB scratch overlay, which was removed. Fresh proposal generation and provider costs remain unverified.
