# Transfer the ARC-selected CPO opening to language archives

The ARC-AGI root replay selected uniform validation on both calibration folds at both roster sizes. This replay carries the same `uniform/8/18` opening into seven previously recorded BBH, LMentry, and MMLU cohorts without tuning it on those cases. It runs the packaged fixed-opening API for all 2,048 three-cycle episodes, with the same prompts, case splits, rosters, and independent qualification as adaptive full-roster CPO. The adaptive traces reproduce exactly. [ARC selection](full-roster-fixed-opening.md) · [Runner](fixed-opening-episode.md) · [Benchmark](../benchmarks/fixed_opening_language_transfer.py)

Each score and cost is held-out passes and charged lookups. The GEPA column gives the upper bound from the previously measured subject-tuned native menu at the fixed arm's realized cost. Its affordable replayed anchor and exact paired range are in the receipt. The simple control can choose uniform or halving per subject under that same cost. The seven cohorts overlap in some archive cases. [Sealed replay receipt](fixed-opening-language-transfer-v1.json)

| Cohort | Adaptive CPO | Fixed uniform | GEPA pass upper bound | Subject-tuned simple |
| --- | ---: | ---: | ---: | ---: |
| Additional MMLU | 7,398 / 5,246 | 7,395 / 6,479 | 7,399 | 7,405 / 5,354 |
| Bounded BBH | 6,326 / 11,549 | 6,332 / 12,618 | 6,350 | 6,390 / 12,320 |
| Bounded LMentry | 6,403 / 14,428 | 6,499 / 13,473 | 5,931 | 6,144 / 13,359 |
| Bounded MMLU | 7,715 / 5,072 | 7,714 / 6,302 | 7,717 | 7,732 / 6,001 |
| Four-case MMLU | 22,366 / 9,114 | 22,365 / 9,987 | 22,369 | 22,408 / 9,958 |
| Tie BBH | 2,140 / 11,974 | 2,109 / 11,507 | 2,126 | 2,159 / 11,170 |
| Tie LMentry | 997 / 6,734 | 1,016 / 6,180 | 919 | 1,005 / 6,094 |

Fixed uniform improved both LMentry cohorts against adaptive CPO. The paired 95% case ranges were +45 to +145 and +1 to +37 passes, respectively, at lower cost. It also exceeded the GEPA upper bounds in both cohorts. Against the simple control, the paired ranges were +284 to +420 on bounded LMentry and −5 to +28 on tie LMentry. Fixed uniform saved 467 lookups on tie BBH and lost 31 passes, with a paired range of −60 to −3. Every MMLU cohort spent more for slightly fewer passes.

Across the measured mix, fixed uniform gained 85 passes and spent 2,429 additional lookups. Where the adaptive arm already chose uniform, all 784 episodes kept the same decisions and saved the two training replies. The 558 episodes where adaptive CPO chose narrow halving accounted for 7,569 additional lookups, offsetting savings in the other opening groups. The replay supports keeping fixed uniform as a task-calibrated option. A blanket switch for these language cohorts would increase cost and lose score on some tasks. Fresh-model superiority remains open.

## Reproduce offline

Use Python 3.12 with the hash-pinned GEPA 0.1.4 wheel. Run the CLI without arguments to preview the seal.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.fixed_opening_language_transfer \
  --execute a765a30487b01f54a2681d2afb05647e699049a6e43ee12e83c4d14803fd4a8d \
  --out NEW_REPORT.json
```

Two runs with DNS and sockets blocked produced byte-identical receipts. All 25 focused tests passed. The CLI rejected a stale seal and preserved a previously written output. The replay sent zero provider requests. Storage Guard measured 9.3 GiB free. The source export, wheel overlay, and publication worktree used 122 MiB under the standing 0.2 GiB LAB exception. [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
