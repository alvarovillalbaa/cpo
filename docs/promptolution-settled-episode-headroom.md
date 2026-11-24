# Bound the Promptolution controls with per-episode hindsight

The frozen CPO transfer compared each runner with the strongest fixed setting within its realized lookup budget. This analysis gives the tested controls a stronger comparison. It lets them choose one setting separately for each episode after seeing its final held-out score and cost. Retaining the starting prompt is always available. All methods and case assignments come from the prior sealed transfer. Every arm reproduces its original paid trace, score, and cost before the optimization. [Original matched-budget replay](promptolution-settled-episode-transfer.md) · [Ceiling runner](../benchmarks/promptolution_settled_episode_headroom.py)

The exact frontier computes the least paid cost for every nondominated aggregate score, then replays the settings that attain each requested point. The GEPA menu contains the 11 native sequential and same-parent batched settings plus retention. The broader menu also includes the two witness variants and five successive-halving settings. The receipt preserves the attaining method for each episode and the minimum cost required to meet each CPO score, when reachable.

## Headroom at each CPO budget

The table shows passes and paid lookups. Each hindsight result is within the corresponding CPO runner's budget for that scope. Both runner budgets reach the same ceilings here.

| Scope | Settled CPO | Feedback CPO | Per-episode GEPA and retention | Per-episode broader menu |
| --- | ---: | ---: | ---: | ---: |
| GSM8K | 2,472 / 906 | 2,451 / 883 | 2,481 / 845 | 2,605 / 790 |
| SST‑5 | 1,452 / 1,549 | 1,434 / 1,465 | 1,421 / 1,128 | 1,536 / 967 |
| **Pooled** | **3,924 / 2,455** | **3,885 / 2,348** | **3,902 / 1,973** | **4,141 / 1,757** |

Per-episode choice adds 337 pooled passes over the best affordable fixed GEPA setting. Settled CPO stays 22 passes above the resulting pooled GEPA ceiling. It trails GEPA hindsight by nine on GSM8K and leads by 31 on SST‑5. Feedback CPO trails the pooled GEPA ceiling by 17. Assigning each task its own budget reproduces the same pooled ceilings.

The broader menu has 217 pooled passes of headroom over settled CPO. Its least expensive hindsight allocation that matches the settled score uses 959 lookups, compared with 2,455 for settled CPO. The tested GEPA menu cannot reach the settled pooled score even when its lookup cap is removed. This is a ceiling over the measured menu, rosters, and archived episodes. It leaves unseen GEPA configurations, new prompt generation, and live performance unverified. [Exact results and attaining allocations](promptolution-settled-episode-headroom-v1.json)

## Reproduce offline

Use the same pinned Promptolution corpus and GEPA 0.1.4 environment as the prior transfer.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.promptolution_settled_episode_headroom \
  --corpus PREDICTIONS.json \
  --execute 98e595afb71bdb83b008d242b51348c203e93fd2503504927738afaf7c4e5dd8 \
  --out /tmp/promptolution-settled-headroom.json
```

Two offline replays produced identical receipts. All 59 focused tests passed, including exhaustive checks of maximum scores, minimum costs, and their attaining allocations. Storage Guard measured 4.7 GiB free. The disposable source, corpus copy, wheel overlay, and publication checkout fit the standing 0.2 GiB LAB exception and were removed. No provider requests were made. [Tests](../tests/unit/test_promptolution_settled_episode_headroom.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
