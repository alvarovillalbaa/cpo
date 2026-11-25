# Choose the CPO opening from paid validation replies

The [fixed-uniform transfer](fixed-opening-language-transfer.md) spent most of its extra lookups where adaptive CPO chose narrow halving. This replay reads the first incumbent validation grade in the episode. A miss chooses uniform. A pass triggers a second read, and two passes choose narrow halving. The selected screen can reuse each exact reply. Every read counts against the 19-lookup first-cycle validation cap, including an unused second reply. Independent qualification and the feedback rule after a rejection stay in force. The route uses zero training probes. [Benchmark](../benchmarks/validation_routed_opening.py)

The replay uses all 2,048 three-cycle language episodes and 3,040 AIME and ARC-AGI audit trials from the two original fixed-opening studies. It reproduces the language baseline lookups and decisions by their full trace hashes. On math, it separately replays the previously calibrated controls at their original settings. The route does not fit a schedule to these held-out grades. The replay follows earlier inspection of the same archives. [Results and prior seals](validation-routed-opening-v1.json)

## Language results

Each cell shows held-out passes and paid lookups. Cohorts reuse some archive cases, so the totals describe this measured mix.

| Cohort | Adaptive CPO | Fixed uniform | Validation-routed CPO |
| --- | ---: | ---: | ---: |
| Additional MMLU | 7,398 / 5,246 | 7,395 / 6,479 | 7,395 / 5,490 |
| Bounded BBH | 6,326 / 11,549 | 6,332 / 12,618 | 6,338 / 11,451 |
| Bounded LMentry | 6,403 / 14,428 | 6,499 / 13,473 | 6,504 / 12,927 |
| Bounded MMLU | 7,715 / 5,072 | 7,714 / 6,302 | 7,711 / 5,478 |
| Four-case MMLU | 22,366 / 9,114 | 22,365 / 9,987 | 22,365 / 8,798 |
| Tie BBH | 2,140 / 11,974 | 2,109 / 11,507 | 2,122 / 11,117 |
| Tie LMentry | 997 / 6,734 | 1,016 / 6,180 | 1,013 / 6,053 |
| **Total** | **53,345 / 64,117** | **53,430 / 66,546** | **53,448 / 61,314** |

The route chose halving in 513 episodes. On bounded LMentry, it added 101 passes over adaptive CPO and saved 1,501 lookups. The paired 95% case range was +49 to +152 passes. At its lookup budget it exceeded the native GEPA upper bound by 573 passes and the subject-tuned simple control by 405 passes, with a paired case range of +344 to +467 against the simple control. Additional MMLU and bounded MMLU still favored the adaptive arm on both point score and cost.

## Math results

| Setting | Adaptive CPO | Calibrated CPO | Validation-routed CPO | Calibrated GEPA or retention |
| --- | ---: | ---: | ---: | ---: |
| AIME root, four | 316 / 1,082 | 311 / 611 | 313 / 850 | 311 / 518 |
| AIME root, eight | 313 / 1,006 | 311 / 502 | 313 / 807 | 311 / 518 |
| AIME rotated, four | 2,538 / 7,909 | 2,542 / 7,922 | 2,541 / 7,246 | 2,506 / 7,848 |
| AIME rotated, eight | 2,537 / 7,653 | 2,526 / 5,156 | 2,533 / 7,180 | 2,503 / 2,658 |
| ARC-AGI root, four | 1,051 / 1,262 | 1,108 / 1,119 | 1,088 / 1,068 | 769 / 1,217 |
| ARC-AGI root, eight | 972 / 1,108 | 1,042 / 875 | 1,042 / 875 | 432 / 0 |
| ARC-AGI rotated, four | 10,612 / 4,934 | 10,612 / 4,934 | 10,598 / 3,791 | 10,378 / 4,792 |
| ARC-AGI rotated, eight | 10,568 / 4,376 | 10,561 / 3,958 | 10,569 / 3,949 | 10,305 / 4,073 |

On rotated ARC-AGI at eight challengers, the route gained 264 passes and saved 124 lookups over the calibrated GEPA control. The paired 95% range was +181 to +347. The four-challenger rotation gained 220 passes and saved 1,001 lookups, with a range of +152 to +288 against that control. On AIME, every paired range against the calibrated control included zero. The eight-challenger AIME rotation still took 4,522 more lookups than that control. The route is available here as a reproducible benchmark. Fresh-model superiority remains open.

## Reproduce offline

Use Python 3.12 with the hash-pinned GEPA 0.1.4 wheel. Omit the arguments to preview the seal.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.validation_routed_opening \
  --execute addc08c289fb2032b03fba4e63cc042d56cebaaa3c82dbb27b782bc1984a3d36 \
  --out NEW_REPORT.json
```

Two network-disabled runs produced byte-identical receipts. All 29 focused tests passed, including proof closure before search, unused reply accounting, and exact prefix reuse. The CLI rejected a stale seal and preserved an existing output. The replay sent zero provider requests. Storage Guard measured 9.1 GiB free. The source export, pinned wheel overlay, and publication worktree occupied 122 MiB under the standing 0.2 GiB LAB exception. [Routing tests](../tests/unit/test_validation_routed_opening.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
