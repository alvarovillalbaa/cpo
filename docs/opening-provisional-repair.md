# Let a tied repair supply context for one more proposal

The second-repair policy missed nine critical passes in one dispatch panel. Its first repair tied every validation row and could neither advance nor supply context for the next proposal. This replay allows a provisional parent when the rejected repair preserves the exact pass pattern and matched-field count on each row. The last accepted candidate remains the fallback. Only a strict improvement over that candidate can enter independent qualification. [Second repair benchmark](opening-second-repair.md) · [Runner](../benchmarks/opening_provisional_repair.py)

The protocol replays the 30 published panels and adds 30 panels from two new seeds. Both cohorts use the same typed rule generator, five opening conditions, and 56-lookup search cap. The inputs are disjoint across cohorts. There are at most two later proposals. Before the second proposal, search must fund a full validation check and uses different training cases from the first repair. The acceptance gate requires preserved passes in each panel, preserved matched critical passes, at least 14 passes in each panel, and either an eight-pass gain at equal or lower cost or a 10% call saving.

## Results

| Method | Prior panels passes / calls | New panels passes / calls |
| --- | ---: | ---: |
| Opening screen | 411 / 1,613 | 411 / 1,611 |
| One repair, standard probes | 508 / 1,846 | 475 / 1,809 |
| One repair, instruction-only probes | 508 / 1,865 | 494 / 1,852 |
| Up to two strict repairs | 531 / 1,925 | 518 / 1,906 |
| Up to two repairs with provisional context | 540 / 1,940 | 524 / 1,921 |
| Adaptive CPO | 529 / 1,929 | 520 / 1,987 |
| Sequential GEPA | 520 / 2,032 | 507 / 2,050 |
| Batched GEPA | 411 / 2,108 | 411 / 2,106 |

One provisional parent advanced to a successful second repair in each cohort. Compared with two strict repairs, this added nine holdout passes on the prior panels and six on the new panels, for 15 additional calls in each. The prior cohort reached 540 of 540 and cleared both GEPA gates.

On the new panels, the policy gained 17 aggregate passes and used 129 fewer calls than sequential GEPA. It still lost 12 matched critical passes. The two failing wrong-rule panels accounted for 11 losses. Full validation exposed errors in those openings, while both selected training probes passed and the first repair remained idle. Another critical loss came from a two-omission panel where the permitted second set of probes also passed. These results distinguish the tied-parent failure from a training probe that misses the failing input regime. The primary gate on the new cohort remains unmet. [Profile outcomes, costs, and gate results](opening-provisional-repair-results-v1.json)

## Reproduce offline

Use pinned GEPA 0.1.4 and a fresh output path.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.opening_provisional_repair
PYTHONHASHSEED=0 python -B -m benchmarks.opening_provisional_repair \
  --execute 6e55c1bb8a51784541a83ffeea306fd489c91e3c6e7e6d2ad9fcf75dfe1af973 \
  --out NEW_REPORT.json
```

Two clean source replays blocked sockets and DNS and matched byte for byte. Each reproduced the published second-repair control and exercised 60 typed panels and 120 official GEPA paths. Thirteen focused tests passed, including strict final qualification, rejection of ties that swap passing rows, and retention of the accepted fallback. The CLI rejected a stale seal and preserved an existing report. Storage Guard measured 4.6 GiB free. The 29.2 MB scratch export was removed under the standing LAB exception. These are scripted fixture results. Live model quality and cost remain unmeasured. [Tests](../tests/unit/test_opening_provisional_repair.py) · [Verification receipt](opening-provisional-repair-verification-v1.json) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
