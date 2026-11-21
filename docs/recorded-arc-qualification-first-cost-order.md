# Price-aware validation in qualification-first ARC-AGI

Qualification-first CPO had the strongest observed CPO score in the eight-challenger ARC-AGI rotation. This replay keeps that policy and changes the order of validation within each challenge. It estimates failures per unit cost from paid replies, using one success and one failure as a prior plus two observations in the direction of the current exact leader's result. It smooths per-case costs with the incumbent's median evaluation cost. Protected critical rows go first. The race still needs an exact validation winner, keeps the original challenger order and training and backup rules, and uses the same qualification. [Earlier ARC comparison](recorded-two-witness-math-transfer.md) · [Runner](../benchmarks/recorded_two_witness_arc_cost_order.py)

The replay checked all 800 validation winners against the qualification-first baseline. They matched. All earlier ARC scores, prices, and the GEPA frontier also reproduced. The table reports the change from ordinary validation order. [Paired paths and matched-cost comparisons](recorded-arc-qualification-first-cost-order-results-v1.json)

| Starting prompts | Ordinary passes / lookups | Price-aware passes / lookups | Historical cost increase |
| --- | ---: | ---: | ---: |
| Original, four challengers | 1,561 / 1,820 | 1,561 / 1,836 | $1.60 |
| Original, eight challengers | 1,578 / 2,020 | 1,578 / 2,045 | $2.06 |
| Rotated, four challengers | 13,761 / 8,439 | 13,761 / 8,516 | $6.36 |
| Rotated, eight challengers | 13,822 / 9,896 | 13,828 / 10,066 | $16.31 |

One deployment changed in the eight-challenger rotation and accounted for all six added passes. The rotation as a whole used 145 extra validation lookups and 26 extra training lookups, with one fewer qualification lookup. Sequential GEPA at cap 44 was the best affordable fixed setting under both price and lookup budgets. It scored 13,784 passes with 9,891 lookups. Price-aware CPO led by 44 passes, with a paired historical-cost range of −8 to +92. The order increased costs in every setting and left the best observed ARC comparison inconclusive. All costs are from archived evaluator charges.

A follow-up kept ordinary validation order and reordered the exact training proof. In the eight-challenger rotation, it preserved every deployment and saved 193 lookups. [Expected training cost comparison](recorded-expected-training-order.md)

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. With DNS and socket connections blocked, 78 targeted tests and five subtests passed. The new test checked exact nomination against all 512 binary outcome grids for three prompts and three cases, including a critical row. Two full replays matched byte for byte. The original selector parity receipt and live-plan preview reproduced. Storage Guard measured 4.6 GiB free. The source export and publication worktree fit the standing 0.2 GiB LAB exception. The replay sent zero provider requests.

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.recorded_two_witness_arc_cost_order
python -B -m benchmarks.recorded_two_witness_arc_cost_order \
  --execute 9b9208aa9675133e7d94d01f18d31f62af6009477383a409394fc5adf928b3ec \
  --out NEW_REPORT.json
```
