# Fit paid search routing with a lookup budget for each discovery cohort

The earlier router fitted one pooled discovery budget. Its transfer results improved the aggregate score and spent more than static CPO on two cohorts. This replay uses the same paid signals and candidate screens. It fits one shared table with a separate lookup budget for each of the eight discovery cohorts. The table observes the position of the incumbent's first qualification miss and its first paid validation grade. The table receives neither task names nor cohort labels when it chooses a screen. [Pooled routing experiment](paid-prefix-archive-routing.md) · [Replay runner](../benchmarks/cohort_budgeted_archive_routing.py)

- **Cohort-budgeted**, the primary, caps each discovery cohort at 95% of its incumbent-first lookups. It maximizes pooled held-out passes subject to all eight caps, then minimizes lookups among ties.
- **Cohort-nonloss** uses each incumbent-first lookup total as its cap and requires at least the incumbent-first score in each discovery cohort. It uses the same pooled objective and tie-break.

The exact search scored both tables on discovery alone. Cohort-budgeted saved 8,925 lookups and lost 25 passes relative to incumbent-first in aggregate. The no-loss control saved 2,247 lookups and gained two passes. Its chosen policy retains the start when the first qualification miss arrives on the fourth case. All other open prechecks choose incumbent-first. These are fitted scores. [Sealed fit and detailed discovery budgets](cohort-budgeted-archive-routing-fit-v1.json)

## Archive replay

The six prior transfer cohorts remain outside fitting. They are a reused evaluation bank. The additional MMLU cohort includes the complete checkpoint pairs for college physics, electrical engineering, college biology, and human aging that had neither appeared in discovery nor in that transfer bank. The runner excludes previously enrolled model and task pairs and preserves the documented case order. Both sets use the unchanged roster, 19-lookup CPO search cap, four-case independent qualification, and disjoint holdout. [Prior transfer bank](shared-validation-archive-transfer.md) · [Additional source archives](low-budget-transfer.md) · [Late-miss archive](late-miss-transfer.md)

Each cell gives held-out passes / paid lookups at one qualification gain. The GEPA column is the best subject-tuned split-safe GEPA setting affordable at the primary's lookup budget.

| Cohort | Fitted static | Pooled router | Cohort-budgeted | Subject-tuned GEPA | Joint gate |
| --- | ---: | ---: | ---: | ---: | --- |
| [Bounded BBH](cohort-budgeted-archive-routing-bounded-bbh-v1.json) | 6,254 / 6,451 | 6,270 / 5,789 | 6,274 / 4,734 | 6,286 / 4,649 | Missed |
| [Bounded LMentry](cohort-budgeted-archive-routing-bounded-lmentry-v1.json) | 5,514 / 6,974 | 5,530 / 6,634 | 5,446 / 6,026 | 5,149 / 5,977 | Missed |
| [Bounded MMLU](cohort-budgeted-archive-routing-bounded-mmlu-v1.json) | 7,705 / 3,187 | 7,716 / 3,114 | 7,717 / 2,702 | 7,716 / 2,026 | Missed |
| [Four-case MMLU](cohort-budgeted-archive-routing-four-case-mmlu-v1.json) | 22,345 / 4,659 | 22,365 / 4,738 | 22,366 / 3,934 | 22,348 / 0 | Passed |
| [Tie BBH](cohort-budgeted-archive-routing-tie-bbh-v1.json) | 2,053 / 4,972 | 2,066 / 4,891 | 2,067 / 4,518 | 2,067 / 4,482 | Missed |
| [Tie LMentry](cohort-budgeted-archive-routing-tie-lmentry-v1.json) | 796 / 2,579 | 822 / 2,673 | 822 / 2,556 | 815 / 2,008 | Passed |
| [Additional MMLU](cohort-budgeted-archive-routing-additional-mmlu-v1.json) | 7,395 / 3,032 | 7,388 / 2,876 | 7,390 / 2,334 | 7,398 / 1,723 | Missed |

The primary saved lookups in all seven cohorts versus fitted static and the pooled router. On the six reused cohorts it gained 25 passes and saved 4,352 lookups versus static. It lost 77 passes and saved 3,369 lookups versus the pooled router. Most of that score loss came from bounded LMentry, where the gap against the pooled policy was −84 passes with a paired range of −105 to −62.

The joint gate requires at most the static cost, a positive paired lower endpoint against static and best affordable common GEPA, and a higher score than the subject-tuned GEPA ceiling. Four-case MMLU gained 18 passes over the ceiling, which retained the start at zero cost. Its paired 95% range was +4 to +33. Tie LMentry gained seven passes over the subject-tuned ceiling, with a paired 95% range of −25 to +38. Its range against best affordable common GEPA was +58 to +117. On additional MMLU the primary saved 698 lookups versus static at five fewer passes, with a paired range of −12 to +2. The no-loss control preserved the static case vector on that cohort and saved 303 lookups. Both policies remain benchmark-only. Fresh-model performance remains unverified.

## Reproduce offline

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. [Benchmark requirements](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.cohort_budgeted_archive_routing --fit NEW_FIT.json
PYTHONHASHSEED=0 python -B -m benchmarks.cohort_budgeted_archive_routing \
  --fitted NEW_FIT.json --cohort additional-MMLU \
  --execute f18ff3e875a116034c6e9e4f655387002ccb1551301a7985bcc5a8f2ad93f932 \
  --out NEW_REPORT.json
```

Two fits and two DNS- and socket-blocked replays per cohort matched byte for byte. The repeated cohorts reproduced all incumbent-first, certified-wide, fitted static, pooled router, and native GEPA totals and traces required by their prior receipts. Thirty targeted tests passed, including exhaustive checks of the constrained fit on mock data. The eight additional panels passed a separate disjointness check on all 256 paired schedules. Storage Guard measured 10.2 GiB free at preflight. The export, wheel overlay, and publication checkout fit the standing 0.2 GiB LAB exception. [Targeted tests](../tests/unit/test_cohort_budgeted_archive_routing.py) · [LAB storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
