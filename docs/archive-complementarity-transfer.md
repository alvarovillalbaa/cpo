# Rank archived prompts by earlier paired gains

The fixed-pool transfer normally retries the most recent eligible archived prompt. This experiment checks whether earlier qualification replies can identify a more complementary candidate. It preserves the eligible archive, permits one directed attempt per incumbent and nominee, and tests the nominee on the current cycle's independent qualification panel. [Archive policy](prompteval-archive-cycles.md) · [Fixed-pool API](fixed-pool-cycle.md)

The paired-wins policy counts cases where the archived prompt passed and the current incumbent failed. It uses only prior paid rows that both prompts answered. It divides wins by the number of observed pairs plus two, breaks ties by the similarly normalized net gain, and then uses recency. Missing replies contribute no pair. The require-win variant skips nominees with zero observed wins.

The archive-disabled control was added after the first three results to test whether skipping archive attempts explained the cost difference. It runs fresh search directly on every cycle. The final replay checks that the first three policies reproduce their original results.

Each arm retains only the qualification replies its callbacks actually read, including earlier archive checks. The ranking uses no new lookups and has no access to the current qualification outcomes before nomination. An archive promotion still requires a strict gain on the new qualification cases. A rejected archive attempt reduces the remaining search budget by its challenger lookup count. Fresh search calls the public deferred first-gain cycle.

The 32-panel replay reproduces the original recency control's callback trace, scores, and paid lookup totals. The sequential and batched GEPA references use their published paid-cap results and original recency archive rule. [Paid-cap GEPA comparison](gepa-paid-cap-transfer.md) · [Runner](../benchmarks/archive_complementarity_transfer.py)

## Results

| Archive policy | Final holdout passes | Paid lookups | Archive attempts | Both GEPA gates |
| --- | ---: | ---: | ---: | ---: |
| Recency | 21,023 | 101,034 | 1,264 | 15 / 32 |
| Paired wins | 20,997 | 100,968 | 1,264 | 14 / 32 |
| Require a paired win | 21,031 | 95,305 | 394 | 10 / 32 |
| Archive disabled, exploratory | 20,988 | 93,369 | 0 | 10 / 32 |

Ranking by earlier paired wins changed 40 nominations on its realized paths. It lost 26 passes and saved 66 lookups against recency. Requiring a prior win reduced archive attempts from 1,264 to 394, gained eight aggregate passes, and saved **5,729 lookups (5.67%)**. Its gain came from the BBH and LMentry stress cohort. It lost 35 passes on MMLU and 12 on the other BBH and LMentry cohort.

Disabling the archive saved a further 1,936 lookups and lost 43 passes against require-win. Within the observed cohorts, skipping most attempts accounts for much of the saving. Retaining attempts with prior paired gains recovered some of the quality lost with the archive disabled. Both policies met the matched gates on 10 panels. The original recency policy had the broadest panel-level success.

These comparisons use recorded correctness and reuse final holdout cases across seeds. The archive ranking policies remain benchmark options. Both offline runs of each phase produced byte-identical reports, and the original three policy traces reproduced exactly after adding the archive-disabled control. [Sealed panel results](archive-complementarity-transfer-results-v1.json)

## Reproduce

Use pinned GEPA 0.1.4. Preview a phase to get its seal, then add `--execute PLAN_SHA256 --out NEW_REPORT.json`.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.archive_complementarity_transfer --phase mmlu
```

The other phases are `bbh-lmentry` and `bbh-lmentry-stress`.
