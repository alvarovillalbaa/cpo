# Use the four-anchor race after a witness search finds no nominee

Choosing the wider race from two incumbent replies missed the transfer gate. This replay keeps the full rotating witness search and uses the four-anchor race only where the existing policy would run Halving. The fallback uses the same cycles and proposal order, reuses the paid witness grades, and charges each new grade once across all cycles. [Opening-route budget comparison](witness-anchor-routing-budget.md) · [Replay runner](../benchmarks/witness_anchor_fallback.py)

The primary arm uses the same 16-new-lookup ceiling as Halving. The second arm allows eight new lookups. Each cycle runs the exact score-bound race on its four seeded validation cases. The first challenger with a settled win advances to the original independent proof. If the next required purchase exceeds the shared cap, the incumbent stays in place. The search cannot start another proof after rejection.

The replay verifies the original seeded and expected-read controls against their published totals and panel traces. The primary arm needs a positive paired 95% lower endpoint against the expected-read control and must remain within the realized seeded lookup ceiling in every cohort. The report also records the best published native GEPA setting affordable at each arm's measured cost.

## Results

| Cohort | Original passes / lookups | 16-new-lookup fallback passes / lookups | 8-new-lookup fallback passes / lookups | Seeded lookup ceiling |
| --- | ---: | ---: | ---: | ---: |
| BBH and LMentry | 17,068 / 71,071 | 16,929 / 71,163 | 16,908 / 68,934 | 72,534 |
| MMLU prior subjects | 21,180 / 34,122 | 21,173 / 34,825 | 21,174 / 32,776 | 34,343 |
| MMLU additional subjects | 8,976 / 13,639 | 8,981 / 13,920 | 8,980 / 13,275 | 13,754 |

The 16-lookup arm reused 15,591 grades during fallback. It still reached its cap before settling in 461 of 591 eligible episodes. It nominated 70 challengers and 23 passed independent proof. On BBH and LMentry it lost 139 held-out passes, with a paired 95% interval of −0.587 to −0.092 percentage points. It exceeded the seeded budgets on both MMLU cohorts. The eight-lookup arm fit every cohort's budget and lost 160 BBH and LMentry passes. Neither arm passed the transfer gate. [Exact receipt and matched-cost native GEPA points](witness-anchor-fallback-results-v1.json)

A follow-up initialized the score bounds from all relevant paid grades and tested nominating a challenger at the cap when those bounds proved a strict gain over the incumbent. The extra nominations recovered the BBH and LMentry loss and increased proof spend. [Paid anchor bounds](witness-paid-anchor-bounds.md)

## Reproduce

Use Python 3.12 with the pinned GEPA 0.1.4 wheel. With sockets and DNS blocked, 98 targeted tests passed and two complete replays matched byte for byte. The CLI rejected a stale seal, and the prospective live-plan preview reproduced byte for byte. Storage Guard measured 6.2 GiB free. The temporary export, wheel overlay, and publication worktree used the standing 0.2 GiB LAB exception. The replay made zero provider requests. [Lookup cap and cache tests](../tests/unit/test_witness_anchor_fallback.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.witness_anchor_fallback
python -B -m benchmarks.witness_anchor_fallback \
  --execute ffa2c720b3a79ec4f18e675c9845a44b15843d3d9aa54ba4784fcc21c712a3bb \
  --out NEW_REPORT.json
```
