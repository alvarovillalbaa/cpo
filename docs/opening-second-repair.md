# Fund a second repair when the first leaves errors

The single-repair cycle recovered one missing rule on the policy-transfer fixture. Six panels with two omissions exposed its limit. This replay permits a second repair after an accepted first repair leaves validation errors. It keeps the original 56-lookup search cap, both official GEPA controls, and all 30 seeded panels. [Previous transfer benchmark](opening-repair-policy-transfer.md) · [Runner](../benchmarks/opening_second_repair.py)

The second round reserves enough budget to evaluate a full validation panel, then uses at most two different training cases. The probes evaluate the instruction alone. If a probe fails, its reply can prompt one repair. A repair must improve the exact validation score and preserve critical passes and family scores. Qualification sees only the final complete nominee, including its demonstrations, against the starting incumbent. The earlier one-repair traces are reproduced before the new comparison.

## Results

| Method | Holdout passes / 540 | Counted calls |
| --- | ---: | ---: |
| Opening screen | 411 | 1,613 |
| One repair, standard probes | 508 | 1,846 |
| One repair, instruction-only probes | 508 | 1,865 |
| Up to two repairs | 531 | 1,925 |
| Adaptive CPO | 529 | 1,929 |
| Sequential GEPA | 520 | 2,032 |
| Batched GEPA | 411 | 2,108 |

The new arm accepted a second repair in four panels and reproduced the one-repair path in the other 26. It recovered 23 holdout passes, all in the two-omission condition, at a cost of 56 validation and training lookups plus four proposals. It gained 11 passes and used 107 fewer calls than sequential GEPA, but lost nine matched critical passes in one panel and missed the gate.

The nine losses came from dispatch, seed 57143. The first repair tied its parent at 10 of 12 exact validation passes and 46 of 48 matched fields. It preserved every exact pass and field count by row. With no strict gain, it was rejected and the second round stayed closed. This identifies the remaining failure as an eligibility decision before the second repair. [Profile outcomes, counts, and gate results](opening-second-repair-results-v1.json)

## Reproduce offline

Use pinned GEPA 0.1.4 and a fresh output path.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.opening_second_repair
PYTHONHASHSEED=0 python -B -m benchmarks.opening_second_repair \
  --execute 2fe7580631eef678540fa87f66ae313043f5f571c3945a4cff445fcabc0237a7 \
  --out NEW_REPORT.json
```

Two clean source replays blocked sockets and DNS and matched byte for byte. Each reproduced 60 official GEPA paths across 30 typed panels. Ten focused tests passed, including distinct training probes, single final qualification, the funding bound, and rejection of a critical regression. The CLI rejected a stale seal and preserved an existing report. Storage Guard measured 4.6 GiB free. The 29.1 MB scratch export was removed under the standing LAB exception. The evidence is from the scripted fixture. Live proposal quality and costs remain unmeasured. [Tests](../tests/unit/test_opening_second_repair.py) · [Verification receipt](opening-second-repair-verification-v1.json) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
