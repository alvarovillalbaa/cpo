# Prioritize Halving cycles with paid validation evidence

The witness and Halving protocol spends a shared 16-lookup fallback budget in the original cycle order. This comparison keeps the witness nominations, eligible fallback episodes, candidate rosters, exact Halving selector, and single independent proof. It tests two ways to change which fallback cycle gets the available lookups. [Previous fallback comparison](witness-anchor-fallback.md) · [Runner](../benchmarks/witness_halving_cycle_priority.py)

The primary policy ranks cycles before buying any new grades. It enumerates the cap-eight Halving boards compatible with the paid grades and divides the fraction won by any challenger by one plus the number of missing grades. This fraction weights the possible boards equally. It serves as a priority score. A cycle with a settled challenger takes precedence, and the original order breaks ties. The ablation keeps the original cycle order. Both variants check later cycles from the paid cache if the budget runs out, with no further purchases.

The replay preserves the assigned proof panel and bank order even when a fallback cycle runs earlier. The policy needs a positive paired 95% lower endpoint against both original Halving and the cache-only ablation. Its realized lookup cost must stay within the seeded budget on every cohort. The report records the affordable native GEPA comparison separately at each arm's measured cost.

## Results

| Cohort | Original Halving passes / lookups | Cache-only continuation passes / lookups | Ranked cycles passes / lookups | Paired 95% interval against original |
| --- | ---: | ---: | ---: | ---: |
| BBH and LMentry | 17,068 / 71,071 | 17,068 / 71,071 | 17,070 / 71,029 | 0.000 to +0.019 pp |
| MMLU prior subjects | 21,180 / 34,122 | 21,180 / 34,122 | 21,186 / 34,116 | −0.015 to +0.059 pp |
| MMLU additional subjects | 8,976 / 13,639 | 8,976 / 13,639 | 8,975 / 13,662 | −0.127 to +0.058 pp |

The cache-only continuation reproduced original scores and lookup totals. Ranking saved 61 validation lookups on BBH and LMentry, used 19 more proof lookups, and kept the number of promotions at 48. It gained six passes on the prior MMLU subjects with six fewer total lookups. On the additional subjects it lost one pass and used 23 more lookups. The ranked policy fit all seeded budgets, and every paired interval included zero. The comparison missed the transfer gate. [Full receipt and matched-cost native GEPA points](witness-halving-cycle-priority-results-v1.json)

A follow-up recalculated cycle priority after each new reply and measured the exact hindsight ceiling for starting one cycle directly. [Interleaved search and direct-cycle ceiling](witness-halving-interleave.md)

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. With sockets and DNS blocked, 104 targeted tests passed and two complete replays matched byte for byte. The CLI rejected a stale seal, and the prospective live-plan preview reproduced byte for byte. Storage Guard measured 5.9 GiB free. The 39 MiB export and bounded publication worktree used the standing 0.2 GiB LAB exception. The comparison made zero provider requests. [Priority and shared-budget tests](../tests/unit/test_witness_halving_cycle_priority.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.witness_halving_cycle_priority
python -B -m benchmarks.witness_halving_cycle_priority \
  --execute 8dc684d5a3f6a780c02f64efe063512aa54f7aeb239c1a6d09caa615a3cd2b6d \
  --out NEW_REPORT.json
```
