# Test a paid repair before widening validation

Ungated widening recovered held-out passes on ARC-AGI and GSM8K and lost passes on SST-5. This replay tests whether the short validation screen gives enough evidence to spend up to six extra reads. A paid repair is a case where the incumbent failed and a challenger passed. The primary gate requires one repair. A second gate also requires that the same challenger have at least as many paid paired wins as losses. The third can spend one of the six reads to grade an unmeasured challenger on the first short-panel incumbent miss with an unread challenger. It reserves that read and has up to five further reads available. Each variant keeps short-panel nominees, requires a strict full-panel gain for a wider nomination, and uses the existing independent qualification. [Ungated experiment](first-gain-validation-tail.md) · [Prior paired audit](first-gain-tail-paired-audit.md) · [Runner](../benchmarks/first_gain_tail_witness.py)

## Archived results

Each cell gives held-out passes and paid lookups. The replay verified all previous results and layouts across 824 archived episodes. It independently checked the positive qualification margin on every tracked promotion.

| Archive | Fixed three cases | Ungated six extra reads | Paid repair | Balanced paid repair | One optional scout |
| --- | ---: | ---: | ---: | ---: | ---: |
| AIME original | 498 / 379 | 498 / 424 | 498 / 389 | 498 / 389 | 498 / 385 |
| AIME rotated | 4,069 / 2,771 | 4,073 / 3,298 | 4,066 / 2,877 | 4,066 / 2,877 | 4,069 / 2,824 |
| ARC-AGI original | 1,338 / 433 | 1,370 / 451 | 1,338 / 433 | 1,338 / 433 | 1,338 / 433 |
| ARC-AGI rotated | 13,491 / 2,374 | 13,515 / 2,499 | 13,491 / 2,382 | 13,491 / 2,382 | 13,491 / 2,379 |
| Promptolution GSM8K | 2,379 / 653 | 2,404 / 682 | 2,379 / 664 | 2,379 / 664 | 2,379 / 664 |
| Promptolution SST-5 | 1,440 / 949 | 1,413 / 1,069 | 1,440 / 949 | 1,440 / 949 | 1,440 / 949 |
| **Total** | **23,215 / 7,559** | **23,273 / 8,423** | **23,212 / 7,694** | **23,212 / 7,694** | **23,215 / 7,634** |

Against ungated widening, every gate recovered 27 held-out passes and saved 120 lookups on SST-5. The 95% paired question-resampled range was +7 to +47 passes. Every gate also lost 32 passes on original ARC-AGI, 24 on rotated ARC-AGI, and 25 on GSM8K. The corresponding ranges were −41 to −23, −33 to −15, and −40 to −10. The one-scout policy matched the fixed panel's score in all six groups and used 75 more lookups in total. The fixed panel remains the better low-cost choice in this archive. The paid short-panel repairs do not support a general widening gate. Fresh-model results remain open. [Sealed results and paired ranges](first-gain-tail-witness-v1.json)

## Reproduce offline

Use Python 3.12, the hash-pinned GEPA 0.1.4 wheel, and the reduced Promptolution corpus named in the receipt. Run without arguments to print the plan seal.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.first_gain_tail_witness \
  --corpus PATH_TO_PINNED_PROMPTOLUTION_CORPUS \
  --execute 45ea39f204f08663b85124deab6b664cb2dee2e6f40a33833cde1670175a6056 \
  --out NEW_REPORT.json
```

Two socket- and DNS-blocked replays produced byte-identical receipts at SHA-256 `fb2444817acb67ad8c867bd0ea0a21ec62ac70657facd9b19f1f823a842c8edb`. All 41 focused tests passed, including exhaustive four-case boards, the six-read limit, and exact widened nominations. The CLI refused a stale seal, an occupied output path, and a changed corpus. Storage Guard measured 8.3 GiB free. The temporary source export, pinned wheel overlay, and publication worktree fit within 0.16 GiB under the standing LAB exception. Zero provider requests were sent. [Tests](../tests/unit/test_first_gain_tail_witness.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
