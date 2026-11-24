# Skip replies that cannot change a frozen search decision

The cohort-budgeted experiment supplied three frozen routing tables. Each table selects a search action from the position of the incumbent's first independent qualification miss and the first incumbent validation grade. This replay leaves the tables fixed and changes when the runner requests those two signals. [Prior fit and results](cohort-budgeted-archive-routing.md) · [Runner](../benchmarks/short_circuit_archive_routing.py)

- If both possible grades on the first validation case select the same screen, start that screen directly. The screen still reads the case if its ordinary procedure needs it.
- After a prefix of incumbent passes, stop the qualification precheck if every remaining possible first-miss position selects retention for both possible validation grades. The rejection receipt records the paid prefix and the remaining gain bound. The policy can keep the incumbent before its qualification gain has been proven impossible.

When a branch can still lead to search, the runner reuses the already paid incumbent prefix. Every nominated challenger must have the original independent qualification observations in the original order. The replay checks each nomination and deployment, and checks that each omitted callback was an incumbent lookup from the original paid path.

## Results

The audit matched all **6,144** old and new outcomes across three policies and 2,048 episodes per policy. The pooled router and the cohort-nonloss router each skipped 373 independent qualification lookups and 119 validation lookups. All savings came from the routes that keep the incumbent after three qualification passes. The cohort-budgeted table uses distinct actions for both probe outcomes at every possible first-miss position and already needs those replies.

| Cohort | Lookups skipped per eligible policy | Cohort-nonloss lookups before → after | Cohort-nonloss holdout passes |
| --- | ---: | ---: | ---: |
| [Bounded BBH](short-circuit-archive-routing-bounded-bbh-v1.json) | 76 | 6,200 → 6,124 | 6,254 |
| [Bounded LMentry](short-circuit-archive-routing-bounded-lmentry-v1.json) | 51 | 6,876 → 6,825 | 5,512 |
| [Bounded MMLU](short-circuit-archive-routing-bounded-mmlu-v1.json) | 99 | 2,902 → 2,803 | 7,705 |
| [Four-case MMLU](short-circuit-archive-routing-four-case-mmlu-v1.json) | 130 | 4,419 → 4,289 | 22,345 |
| [Tie BBH](short-circuit-archive-routing-tie-bbh-v1.json) | 15 | 4,860 → 4,845 | 2,053 |
| [Tie LMentry](short-circuit-archive-routing-tie-lmentry-v1.json) | 0 | 2,579 → 2,579 | 796 |
| [Additional MMLU](short-circuit-archive-routing-additional-mmlu-v1.json) | 121 | 2,729 → 2,608 | 7,395 |

On additional MMLU, the optimized no-loss route matches all 256 static CPO deployments at 2,608 lookups versus 3,032. Subject-tuned GEPA scored 7,398 passes on 1,723 lookups. For the pooled router on bounded LMentry, the smaller budget lowered the attainable native ceiling from 5,213 to 5,204. The router kept its 5,530 passes and used 6,583 lookups. Cohort-budgeted passed its original gate in two of seven cohorts. The optimization remains benchmark-only. Fresh-model performance remains unverified. [Prior controls and gate](cohort-budgeted-archive-routing.md)

## Reproduce offline

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Preview a cohort to get its seal. [Benchmark requirements](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.short_circuit_archive_routing --cohort additional-MMLU
PYTHONHASHSEED=0 python -B -m benchmarks.short_circuit_archive_routing \
  --cohort additional-MMLU \
  --execute 07533293cbe4df357a19af2e51372e6fa2bfb453a7e83fb1ccc722209f0c13ab \
  --out NEW_REPORT.json
```

Two source replays per cohort matched byte for byte with DNS and outbound sockets blocked. The full native GEPA subject totals reproduced before repricing. Thirty-three targeted tests passed. The new tests exhaustively compare small boolean prechecks and cover retention before an otherwise unread miss. Storage Guard measured 10.2 GiB free at preflight. The export, wheel overlay, and publication checkout fit the standing 0.2 GiB LAB exception. [Focused tests](../tests/unit/test_short_circuit_archive_routing.py) · [LAB storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
