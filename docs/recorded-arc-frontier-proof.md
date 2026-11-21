# Certifying GEPA parent draws within the quoted budget

CPO can certify GEPA 0.1.4's next parent for pools of three to seven distinct prompts on up to 32 validation cases. It considers the case winners compatible with the grades already read and every survivor set GEPA could prune to. It stops reading when every outcome gives the same parent and leaves the random generator in the same state. The ARC replay compares validation order, reading the most uncertain cases first, and validation order with reserve settlement. It uses the same recorded child availability, quotes, and held-out cases as the matched native GEPA comparison. [Sealed result](recorded-arc-frontier-proof-results-v1.json) · [Native controls](recorded-arc-native-empty-slots.md)

When a round would exceed the price ceiling, `settle_validation_on_price_limit=True` lets the sequential selector read grades it already reserved at their maximum price. A cheaper reply releases the difference. The selector stops as soon as it can fund the whole round or the settled charges make it unaffordable. It checks the independent proposal ceiling before settling grades. The option requires a `SequentialSearchBudget` and is off by default. [Sequential selector](../cpo/sequential_field_rewrite.py)

## Recorded ARC

Each budget and price combination covers 200 paths and 9,600 held-out uses of the same 80 cases. Cost below covers recorded search and admission evaluations. Proposal charges were modeled separately. All three proof variants matched the parent draws and training minibatches they shared with the prior CPO schedule. At each price point, 20 paths reached a pool of at least three prompts.

| Budget and proposal price | CPO policy | Held-out passes | Search reads | Recorded evaluation cost |
| --- | --- | ---: | ---: | ---: |
| 32 quotes, 1× | Prior CPO | 6,662 | 2,856 | $408.60 |
| | Validation order with settlement | 6,662 | 2,837 | $406.16 |
| | Most uncertain cases first | 6,662 | 2,836 | $405.84 |
| 32 quotes, 4× | Prior CPO | 6,638 | 2,818 | $403.77 |
| | Validation order | 6,636 | 2,773 | $398.97 |
| | Most uncertain cases first | 6,636 | 2,790 | $400.89 |
| | Validation order with settlement | 6,638 | 2,807 | $402.29 |
| 60 quotes, 1× or 4× | Prior CPO | 6,662 | 2,856 | $408.60 |
| | Validation order with settlement | 6,662 | 2,837 | $406.16 |
| | Most uncertain cases first | 6,662 | 2,843 | $406.93 |

At 32 quotes and the four-quote proposal price, the proof alone left more unread grades at their maximum quotes. Both read orders lost two net passes on one path. Settlement restored the prior CPO schedule, nominees, admission decisions, and every held-out outcome across all four settings. It saved 11 to 19 search reads and $1.47 to $2.44 in pooled evaluation cost per setting. One path used more reads and cost more at the tightest setting. At the other three settings, settlement produced the same results as the validation-order proof alone.

At 60 quotes and the four-quote proposal price, CPO with settlement passed 6,662 cases at $406.16 in recorded evaluation cost. Sequential GEPA passed 6,657 at $522.49 and batched GEPA passed 6,523 at $531.43. The paired case-block ranges were −3 to +13 and +110 to +171, respectively. The sequential comparison remains inconclusive on held-out quality. All results use archived grades and recorded rewrite lineages. Fresh proposal quality remains unverified.

## Scripted width-two control

Reading cases in decreasing order of the number of possible winner sets cut CPO search reads from 1,157 to 1,126 at cap 76. The native parent and minibatch schedule, later proposals, admission, and all 622 held-out passes matched. At caps 32 and 56, both orders used the same number of reads. ARC showed mixed cost effects from this ordering, so the proof keeps validation order by default. [Earlier fixture receipt](batched-field-frontier-bounds-results-v1.json)

## Reproduce offline

Use Python 3.12 and the [hash-pinned GEPA 0.1.4 wheel](../requirements-benchmark.txt). The sealed benchmark checks the two reference receipt hashes and writes only to a fresh path. The recorded run blocked sockets and DNS and sent zero provider requests.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.recorded_arc_frontier_proof
PYTHONHASHSEED=0 python -B -m benchmarks.recorded_arc_frontier_proof \
  --execute ce560c61dd77c74221ac1463d63deeed751361702df3f44d9c3c0bd3a0375467 \
  --out NEW_REPORT.json
```

The result SHA-256 is `742061eb5c3d341fe1090549aa5aa33fad6bb59e58ae4af7c9288314d8c112d1`.

The follow-up compares reordering after each read and a finite-grade proof. Reproduce this original receipt from the revision that added it. [Adaptive case order](gepa-adaptive-case-order.md) · [Original source revision](https://github.com/alvarovillalbaa/cpo/tree/cf50261b1a953f7077481e77658d2d5a31fb0771)
