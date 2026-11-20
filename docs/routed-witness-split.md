# Split the opening probes across two incumbent misses

A separate rescue round after a stalled search recovered some holdout passes at a high lookup cost. This replay spreads the opening probes across the first two validation cases when both are already known incumbent misses. All arms use the original proposal blocks, recency archive, 52-lookup search ceiling, and independent eight-case qualification. [Second-witness rescue](finalist-witness-rescue.md)

## Search policies

The first-witness arms make one screening probe per visited challenger. The shared arm uses the same incumbent miss for every probe. The split arms alternate the two misses by proposal position. They defer the rest of incumbent validation until a challenger passes its witness. The retry arm keeps screening after a rejected certificate and can fund a second certificate. The dual arm reserves a full validation race for the first witness from each miss and chooses the exact validation winner. All validation modes require strict gain and preserve incumbent critical passes.

The route normally keeps deferred first-gain search when the opening two incumbent replies include a pass. One variant uses the earlier bounded-discovery selector on this branch. The two hybrid arms first see two misses, then read a third incumbent case. One invokes the original balanced backup race on a third miss, and the other invokes it on a pass. The complementary branch uses the split retry. The ledger charges each prompt and case pair once during search, including the observations used for routing. [Runner](../benchmarks/routed_witness_split.py) · [Bounded discovery](prompteval-bounded-discovery.md)

## Results

Each cell shows holdout passes / distinct paid search and qualification lookups.

| Policy | BBH and LMentry | MMLU pilot | MMLU model transfer |
| --- | ---: | ---: | ---: |
| Original routed backup | 3,419 / 50,448 | 22,391 / 35,895 | 12,223 / 54,166 |
| Shared miss, one certificate | 3,304 / 35,062 | 22,334 / 30,029 | 12,165 / 46,432 |
| Split misses, one certificate | 3,382 / 36,740 | 22,332 / 30,699 | 12,179 / 47,989 |
| Split misses, retry rejected certificate | 3,388 / 38,320 | 22,332 / 30,919 | 12,190 / 48,912 |
| Split misses, exact dual race | 3,394 / 40,982 | 22,342 / 31,142 | 12,186 / 49,240 |
| Split retry with bounded discovery | 3,390 / 38,868 | 22,338 / 33,253 | 12,204 / 52,315 |
| Widen on third miss | 3,386 / 49,104 | 22,366 / 33,898 | 12,219 / 52,605 |
| Widen on third pass | 3,413 / 39,797 | 22,359 / 33,159 | 12,201 / 50,951 |
| Batched GEPA, cap 52 | 3,396 / 47,537 | 22,352 / 38,990 | 12,181 / 57,817 |
| Sequential GEPA, cap 52 | 3,457 / 65,252 | 22,361 / 56,504 | 12,253 / 83,250 |

On the later MMLU model splits, the split retry led batched GEPA by **nine passes with 15.4% fewer lookups** and trailed sequential GEPA by 63 passes. Widening on a third miss used the balanced race in 235 of 422 two-miss cycles. It scored four passes below the original routed backup and saved 1,561 lookups. It led batched GEPA by 38 passes with 9.0% fewer lookups and finished 34 passes behind sequential GEPA. After dropping any one subject and both of its model panels, the two gaps ranged from +17 to +44 and from −39 to −19, respectively.

Widening on a third pass led batched GEPA on all three cohorts in aggregate. The later MMLU lead was 20 passes with 11.9% fewer lookups, with 52 fewer passes than sequential GEPA. The BBH and LMentry advantage was sensitive to dropping a task. Widening on a third miss beat both GEPA controls on the MMLU pilot, where its five-pass lead over sequential GEPA was also sensitive to dropping a subject. These archived cohorts show that routing can move the search cost and score tradeoff. The strongest sequential GEPA result on the later model splits remains ahead of the new arms. [Full results and panel receipts](routed-witness-split-results-v1.json)

At comparable realized lookup cost, the third-pass route finishes one pass behind sequential GEPA. The follow-up sweeps both GEPA modes across all integer paid caps from 20 through 68. [Matched-cost model frontier](routed-model-cost-frontier.md)

## Reproduce

Use GEPA 0.1.4. Preview each phase for its seal. The other phases are `bbh-lmentry` and `mmlu`.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.routed_witness_split --phase model-transfer
PYTHONHASHSEED=0 python -B -m benchmarks.routed_witness_split \
  --phase model-transfer --execute 81c707d7e4ac012eea3a8a941f48dae70664245f5a32bac5a0c23a5b8504294c \
  --out NEW_REPORT.json
```

Two offline source-export replays per cohort matched byte for byte with sockets and DNS blocked. All 40 routed backup traces matched the published receipts. Four focused tests passed, including 4,096 binary matrices checked at two caps for each split proof policy. The checks cover strict validation gain, critical-case preservation, the reserve for a second proof, and unique lookup accounting. The CLI rejected an incorrect seal. Storage Guard measured 14.1 GiB free. The 12.8 MB scratch overlay was removed under the standing LAB exception. Fresh proposal quality and provider costs remain unverified. [Focused tests](../tests/unit/test_routed_witness_split.py)
