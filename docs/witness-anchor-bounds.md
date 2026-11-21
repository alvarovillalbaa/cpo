# Stop a four-anchor race when the winner is known

The published four-anchor best-score race improved archived BBH and LMentry accuracy and exceeded the seeded lookup budget. This replay tests whether a bounded race can settle the same validation winner with fewer reads. It keeps the four seeded anchors, candidate roster, proposal-order ties, original lookup caps, Halving fallback, and independent proof. [Four-anchor race](witness-matched-anchors.md) · [Replay runner](../benchmarks/witness_anchor_bounds.py)

The race scores the incumbent on all four anchors. A challenger's observed passes give its lower score bound. Every unread anchor contributes one additional possible pass to its upper bound. A prompt is eliminated when its upper bound cannot beat the leader's lower bound under the original tie rule. The race stops when the leader's identity is certain. Its final score can still have unread grades. At the cap, the highest observed lower bound supplies the nominee. The incumbent wins ties and a challenger needs a proved gain to advance.

Smoothed pass rates on each anchor use only paid replies in the current race. They determine read order among contenders. The candidate with the highest projected score goes next. The current leader reads its higher-rate anchors first to raise its lower bound. A rival reads its lower-rate anchors first to test whether it can stay competitive. Exact bounds govern selection. The replay reproduces the earlier best-score policy and compares paired holdout changes against both the original first proof and the best-score race.

## Results

| Cohort | Original first proof passes / lookups | Earlier best-score race passes / lookups | Score bounds passes / lookups | Seeded lookup ceiling |
| --- | ---: | ---: | ---: | ---: |
| BBH and LMentry | 17,068 / 71,071 | 17,348 / 82,961 | 17,348 / 81,169 | 72,534 |
| MMLU prior subjects | 21,180 / 34,122 | 21,216 / 44,184 | 21,216 / 44,091 | 34,343 |
| MMLU additional subjects | 8,976 / 13,639 | 8,950 / 17,277 | 8,950 / 17,187 | 13,754 |

Score bounds settled all 4,166 races. Three settled while the winning prompt still had unread anchors, all on BBH and LMentry. The replay matched the earlier best-score held-out totals and promotions while saving 1,792 lookups on BBH and LMentry and 183 across MMLU. Every paired 95% interval against that best-score control was exactly zero.

The BBH and LMentry result retained the 280-pass gain against the original first proof. Its paired interval was +0.005 to +1.347 percentage points, and it still exceeded the seeded budget by 8,635 lookups. MMLU remained 36 passes ahead on the prior subjects and 26 behind on the additional subjects, with both cohorts above their seeded totals. The score-bound race missed the transfer gate. The comparison used archived grades and sent zero provider requests. [Full costs, paired intervals, and settlement counts](witness-anchor-bounds-results-v1.json)

## Reproduce

Use Python 3.12 with the hash-pinned GEPA 0.1.4 wheel and a clean source export. With sockets and DNS blocked, 88 targeted tests passed and two full replays matched byte for byte. The original scores and charges, four-anchor best-score control outcomes and paired intervals, and the prospective live plan reproduced. The CLI rejected a stale seal. Storage Guard measured 6.3 GiB free. The source export, wheel overlay, and publication worktree used the standing 0.2 GiB LAB exception. [Exact winner and cap tests](../tests/unit/test_witness_anchor_bounds.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.witness_anchor_bounds
python -B -m benchmarks.witness_anchor_bounds \
  --execute 7fbcb18a6ca0f346017557afb9fcd02e43820aa0a29f182b181553d9f26e7658 \
  --out NEW_REPORT.json
```
