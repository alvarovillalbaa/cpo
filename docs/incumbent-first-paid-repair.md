# Check the incumbent before purchasing challenger replies

The paid-repair policy qualifies a certified-wide finalist only if the shared validation grades show it passing a case the incumbent failed. The incumbent-first schedule tests the same policy with a different dispatch order. It reads the incumbent's original shared cases up to the first miss. If it passes them all, a repair is impossible and the runner needs no challenger grades. Otherwise it reuses the paid incumbent replies in the original challenger race. The finalist's independent qualification uses the same grades, order, and stopping condition. [Previous paid-repair policy](paid-validation-agreement.md) · [Replay runner](../benchmarks/incumbent_first_paid_repair.py)

The early check applies only when the cap can cover every scheduled round for the supplied roster. The maximum number of challengers per round and one incumbent reply per round bound the total cost even if the runner prepays a row the original screen would have skipped. Smaller caps and validation panels containing critical cases use the original policy. The wide schedule can add one incumbent lookup if all challengers would have been eliminated before the last shared case. The replay counts that lookup as paid.

The benchmark holds all starts, rosters, and case splits fixed across 134 model panels and 32 schedules per panel. It checks both independent qualification margins and prices every physical reply. [Sealed replay](incumbent-first-paid-repair-results-v1.json)

## Archived results

All 8,576 paths preserved the original finalist or rejection, deployment, ordered qualification receipt, and every held-out grade. The reordered search used 122,854 lookups, down from 128,615. It saved lookups on 715 paths and added one lookup on each of six paths. All other paths had the same cost. Seven cohorts saved lookups at both margins. The ends-with-word cohort had the same costs at both margins.

| Cohort and qualification gain | Held-out passes | Paid repair to incumbent-first lookups | Lookups saved | Exact affordable split-safe GEPA passes / lookups |
| --- | ---: | ---: | ---: | ---: |
| Earlier MMLU, one | 26,646 | 12,569 → 11,435 | 9.0% | 26,655 / 8,574 |
| Disjoint MMLU, one | 56,095 | 11,741 → 10,271 | 12.5% | 56,089 / 6,814 |
| Earlier MMLU, two | 26,633 | 9,167 → 8,624 | 5.9% | 26,655 / 8,574 |
| Disjoint MMLU, two | 56,090 | 8,289 → 7,648 | 7.7% | 56,089 / 6,814 |

The settings that attained the published GEPA ceilings for both MMLU cohorts fit all four new budgets. A lower budget cannot raise those ceilings, so the original attainable scores remain exact. At one gain on disjoint MMLU, CPO still led by six passes with a paired 95% range of −37 to +49 passes and used 3,457 more lookups. At two gains the cost gap fell to 834. The new schedule remains benchmark-only, and fresh-model performance remains unverified. [Paired comparison](paid-validation-agreement.md) · [GEPA budget controls](shared-validation-split-safe-transfer.md)

## Reproduce offline

Use Python 3.12 with the hash-pinned GEPA 0.1.4 benchmark dependency. [Benchmark requirements](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.incumbent_first_paid_repair
PYTHONHASHSEED=0 python -B -m benchmarks.incumbent_first_paid_repair \
  --execute a7b1279c0325901f3648f6286d4d3e21b257e65a771ade5f888de83c6cb4947b \
  --out NEW_REPORT.json
```

Two DNS- and socket-blocked replays produced identical reports at SHA-256 `9e5a822b1215aa31bfb771c0449eac0e040824f7ca5c054dbd7af5f575e60a8e`. Twenty-three targeted tests passed, including exhaustive comparison across 4,096 binary grade matrices at ten caps. A separate seeded check verified 20,480 full-roster matrix-and-cap combinations and observed at most one extra incumbent lookup on a path. Storage Guard measured 2.2 GiB free at preflight. The source export, wheel overlay, and publication checkout fit the standing 0.2 GiB LAB exception. [Targeted tests](../tests/unit/test_incumbent_first_paid_repair.py) · [LAB storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
