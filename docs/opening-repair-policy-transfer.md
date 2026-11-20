# Test one repair across different typed failure patterns

The instruction-only diagnostic passed both GEPA gates on the earlier scripted tasks, whose seeded cohorts reused some inputs. This follow-up exercises the public repair API on dispatch, stock, and service policies with new field mappings. The 30 panels contain 1,620 distinct input strings, including 540 holdout cases. Within each panel, the training, validation, qualification, and holdout splits also use distinct feature combinations. The scripted proposer learns field mappings from the labeled training cases and changes at most one rule per proposal. [Public repair API](opening-repair-cycle.md) · [Earlier diagnostic benchmark](opening-repair-diagnostic.md) · [Runner](../benchmarks/opening_repair_policy_transfer.py)

Each task uses two seeds for five opening conditions. The opening may be complete, omit a rule fully covered by demonstrations, omit one partially covered rule, omit two partially covered rules, or contain a wrong rule. Every arm gets the same opening and demonstrations for its panel. The standard repair probes the complete parent. The instruction-only arm removes demonstrations for those training probes and restores them for validation and qualification. Both repair arms can request at most one later proposal. Adaptive CPO and the two official GEPA modes retain their ordinary proposal settings. The search cap is 56 paid lookups per panel. Counted calls include search, independent qualification, and proposal generation modeled by the fixture.

## Results

| Method | Holdout passes / 540 | Counted calls |
| --- | ---: | ---: |
| Retain start | 0 | 0 |
| Opening screen | 411 | 1,613 |
| One repair, standard probes | 508 | 1,846 |
| One repair, instruction-only probes | 508 | 1,865 |
| Adaptive CPO | 529 | 1,929 |
| Sequential GEPA | 520 | 2,032 |
| Batched GEPA | 411 | 2,108 |

| Opening condition | Standard repair passes / 108 | Instruction-only passes / 108 | Adaptive CPO passes / 108 | Sequential GEPA passes / 108 |
| --- | ---: | ---: | ---: | ---: |
| Complete | 108 | 108 | 108 | 108 |
| One omission fully covered by demonstrations | 108 | 108 | 108 | 108 |
| One partially covered omission | 101 | 108 | 108 | 108 |
| Two partially covered omissions | 83 | 76 | 97 | 88 |
| Wrong rule | 108 | 108 | 108 | 108 |

For one partially covered omission, instruction-only repair gained seven passes over standard repair. It matched both adaptive CPO and sequential GEPA, using 13 and 48 fewer calls, respectively. The 12 panels with either complete openings or full demonstration coverage skipped later repair.

Every holdout loss against sequential GEPA came from the two-omission condition. Instruction-only repair missed 12 aggregate passes and 10 matched critical passes against that control. It saved 167 calls in aggregate, but missed the primary gate, which requires preserved panel totals and critical cases, at least 14 passes in each panel, and either an eight-pass gain without added calls or a 10% call reduction. The one-repair policy recovered a single missing rule reliably in this fixture. The two-omission result supports testing a budgeted second repair when errors remain. [Profile costs, gates, and trace hash](opening-repair-policy-transfer-results-v1.json)

## Reproduce offline

Use pinned GEPA 0.1.4 and a fresh output path.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.opening_repair_policy_transfer
PYTHONHASHSEED=0 python -B -m benchmarks.opening_repair_policy_transfer \
  --execute dd2b2b25de0267de7bca375c45ebfb1f0a893e2d32c452dd6fab901696fb266f \
  --out NEW_REPORT.json
```

Two clean source replays blocked sockets and DNS and matched byte for byte. Each exercised 30 typed panels and 60 official GEPA paths. Thirteen focused tests passed. The runner rejected a stale seal and preserved an existing report. Storage Guard measured 4.6 GiB free. The 29.1 MB scratch export was removed under the standing LAB exception. Live proposal quality and costs remain unmeasured. [Verification receipt](opening-repair-policy-transfer-verification-v1.json) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
