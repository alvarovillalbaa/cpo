# Fixed-roster search controls over three cycles

This replay adds uniform screening and successive halving to the three-cycle comparison with native GEPA. The 2,048 episodes use the original starting prompts, candidate rosters, role-disjoint cases, and fixed final holdout. Both archived CPO policies reproduce their original paid trajectories in every panel. [Three-cycle layouts and native GEPA results](continuous-archive-routing.md)

Each control uses the first four or eight candidates in the frozen roster. A round scores one validation case for the incumbent and every surviving candidate. A round begins only when the remaining cap funds it in full. The halving control keeps the highest-scoring half of the challengers after rounds one, two and four, with ties decided by frozen roster order. The uniform control keeps the whole prefix. A nominee must strictly beat the incumbent on the observed rows and then pass the same independent one-net-gain qualification used by CPO. This gives the controls CPO's qualification precheck and early stopping. The replay charges both validation and qualification reads.

The comparison covers 24 settings and retention. Each setting uses the same cap and roster width in all three cycles. For each cohort, the best common setting per family is selected in hindsight under the routed CPO lookup budget. The subject-tuned ceiling can mix families, widths, caps and retention across tasks under that same pooled budget.

| Cohort | Routed CPO | Common halving | Common uniform | Subject-tuned controls | CPO paired 95% range vs subject-tuned |
| --- | ---: | ---: | ---: | ---: | ---: |
| [Bounded BBH](continuous-search-controls-bounded-bbh-v1.json) | 6,389 / 13,797 | 6,321 / 12,570 | 6,309 / 9,061 | 6,400 / 13,646 | −92 to +69 |
| [Bounded LMentry](continuous-search-controls-bounded-lmentry-v1.json) | 6,321 / 15,711 | 6,040 / 13,650 | 6,040 / 13,650 | 6,349 / 15,660 | −98 to +40 |
| [Bounded MMLU](continuous-search-controls-bounded-mmlu-v1.json) | 7,725 / 7,696 | 7,717 / 7,303 | 7,706 / 0 | 7,733 / 7,355 | −27 to +11 |
| [Four-case MMLU](continuous-search-controls-four-case-mmlu-v1.json) | 22,381 / 12,145 | 22,372 / 11,202 | 22,372 / 11,202 | 22,410 / 11,730 | −47 to −11 |
| [Tie BBH](continuous-search-controls-tie-bbh-v1.json) | 2,204 / 13,130 | 2,138 / 11,541 | 2,111 / 10,071 | 2,174 / 13,022 | −16 to +73 |
| [Tie LMentry](continuous-search-controls-tie-lmentry-v1.json) | 1,028 / 7,195 | 982 / 6,547 | 975 / 6,870 | 1,013 / 6,884 | −12 to +44 |
| [Additional MMLU](continuous-search-controls-additional-mmlu-v1.json) | 7,384 / 7,257 | 7,397 / 5,124 | 7,397 / 5,124 | 7,407 / 6,611 | −41 to −6 |

Cells show final held-out passes and total paid lookups. Tie BBH and tie LMentry retained their earlier gate wins against static CPO and GEPA. Both also beat the best common control from each new family at a positive paired lower endpoint. The advantage fell to 30 and 15 passes against the respective subject-tuned controls, and both ranges crossed zero. The tuned controls scored higher and spent fewer lookups on the other five cohorts. Their advantage had a paired range above zero on four-case and additional MMLU.

The paired ranges resample holdout case IDs within each task and keep all seeds, models and selected settings paired. The schedules use final holdout scores during selection and are held fixed during resampling. The ranges describe the chosen archived comparisons. The controls need a separately fitted configuration to estimate forward performance, and the replay measures selection from supplied prompts with no fresh proposal generation.

## Reproduce offline

Use Python 3.12 with the pinned GEPA 0.1.4 wheel. The first command prints the cohort-specific seal. The second writes a fresh receipt using that seal. [Benchmark requirements](../requirements-benchmark.txt) · [Replay runner](../benchmarks/continuous_search_controls.py)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.continuous_search_controls --cohort tie-LMentry
PYTHONHASHSEED=0 python -B -m benchmarks.continuous_search_controls \
  --cohort tie-LMentry \
  --execute 3a8277dafa9a0dc4c11fa6820eb34e6f5755952db4cf9d7e5ab107f309afdee7 \
  --out NEW_REPORT.json
```

Two replays per cohort matched byte for byte with DNS and outbound sockets blocked. Nine targeted tests passed. A separate budget-indexed calculation reproduced the maximum passes and minimum attaining cost for all seven subject-tuned schedules. Storage Guard measured 10.4 GiB free. The source export, wheel overlay and publication checkout fit the standing 0.2 GiB LAB exception. [Targeted tests](../tests/unit/test_continuous_search_controls.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
