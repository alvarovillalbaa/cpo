# Stop the terminal qualification precheck when another reply costs too much

The capped precheck sometimes paid for qualification replies that neither settled both rejections nor saved enough validation work. This replay replaces its read-order objective with a choice between buying another reply and handing off to the packaged first-gain screen. It keeps the same 824 archived episodes, cases, prompt rosters, exact rejection bounds, and independent qualification gate. All earlier cycle decisions and every final deployment must reproduce. [Capped precheck](first-gain-proof-precheck.md) · [Runner](../benchmarks/first_gain_precheck_stopping.py)

The planner assigns a fixed estimated cost to the handoff. It prices an eligible reply as one lookup plus the model's expected remaining cost. It buys the reply only when this estimate is strictly below the handoff cost. The correlated model weights the two unanimous grade combinations five times as heavily as each mixed combination and conditions on any paid grades on that case. An independent version weights all eight combinations equally. The primary comparison uses a correlated model and an eight-lookup handoff. The twelve-lookup handoff is a sensitivity check. The handoff estimates guide spending. Exact observed grades determine rejection. [Sealed results](first-gain-precheck-stopping-v1.json)

## Results

The table shows paid lookups. Every arm had the same held-out score within each group.

| Archive | Packaged 18-read policy | Earlier unrestricted precheck | Independent, 8 | Correlated, 8 | Correlated, 12 |
| --- | ---: | ---: | ---: | ---: | ---: |
| AIME original | 552 | 520 | 514 | 528 | 497 |
| AIME rotated | 4,282 | 3,789 | 3,944 | 3,895 | 3,808 |
| ARC-AGI original | 614 | 680 | 621 | 616 | 622 |
| ARC-AGI rotated | 2,987 | 2,903 | 2,805 | 2,802 | 2,775 |
| Promptolution GSM8K | 786 | 813 | 798 | 794 | 796 |
| Promptolution SST-5 | 1,392 | 1,339 | 1,385 | 1,363 | 1,340 |
| **Total** | **10,613** | **10,044** | **10,067** | **9,998** | **9,838** |

The correlated twelve-lookup rule saved 775 lookups against the packaged baseline and 206 against the earlier unrestricted precheck. On rotated ARC-AGI, it recorded 13,578 passes in 2,775 lookups. The strongest affordable native GEPA setting recorded 13,461 passes in 2,766. Historical evaluator charges were $363.48 for CPO and $356.20 for that GEPA setting, down from $390.66 for the packaged first-gain policy.

On rotated AIME, the new rule scored 4,080 passes to GEPA's 4,072 while spending 471 more lookups. It used 19 more lookups than the earlier unrestricted precheck. It spent eight additional lookups on original ARC-AGI and ten on GSM8K relative to the packaged baseline. GEPA and halving comparisons use the published control points at each realized budget. The replay uses shared archived prompts, so fresh proposal performance remains unverified.

## Reproduce offline

Use Python 3.12 and the original hash-pinned Promptolution corpus. Run without arguments to preview the seal.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.first_gain_precheck_stopping \
  --corpus PATH_TO_PINNED_PROMPTOLUTION_CORPUS \
  --execute 605aa01008c143daa30632529ffa8035329545280984ed4b2fb9052f5ac76d03 \
  --out NEW_REPORT.json
```

Two socket- and DNS-blocked runs produced byte-identical receipts at SHA-256 `528b3704411f969432c186ae811c5545960b615ebcc29950dcbd31dbe3770b38`. All 22 focused tests passed, including all 4,096 four-case grading boards and the tie that favors handing off before paying for another reply. The CLI refused a stale seal, an occupied output path, and an incorrect corpus. Storage Guard measured 8.4 GiB free. The source export, archive copy, and publication worktree used 126 MiB under the standing LAB exception. Zero provider requests were sent. [Tests](../tests/unit/test_first_gain_precheck_stopping.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
