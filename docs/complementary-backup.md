# Use the failed finalist’s replies to rank tied backups

CPO’s wide validation branch ranks six challengers on two shared cases. It confirms the first-ranked challenger and tries a backup if that challenger fails. The original backup ranking makes no use of the losing finalist’s additional replies. This experiment tests a different tie-break for that backup while preserving the primary finalist and the full exact validation requirement. [Original wide search](finalist-screen-budget.md) · [Runner](../benchmarks/complementary_backup.py)

The new tie-break finds the first case outside the screening pair that both the incumbent and failed finalist were observed to miss. Among challengers tied for the original backup score, it prefers the first one that passes this extra case. It buys evidence only when the remaining cap can still fund a full confirmation of the possible backup or the original fallback. The second arm uses the first additional incumbent miss regardless of the failed finalist’s reply. Both follow the original route and separate qualification. A backup still needs to improve the exact validation total and preserve every incumbent critical pass.

The replay uses the published 16 Llama and Mistral panels and 12 Gemma and Flan panels, with the original 32 four-cycle episodes per panel. The comparison reproduces the existing CPO and official GEPA traces where published. The same gate requires 10% savings against both cap-52 controls and a nonnegative lower endpoint for the joint central 95% paired case range within each cohort. [Cohort provenance and prior controls](case-difficulty-allocation.md)

## Results

Each cell gives holdout passes and total paid search and qualification lookups.

| Method | Llama and Mistral | Gemma and Flan |
| --- | ---: | ---: |
| Original route | 17,724 / 49,330 | 17,435 / 35,496 |
| Additional incumbent miss | 17,724 / 49,761 | 17,434 / 35,749 |
| Miss shared by incumbent and failed finalist | 17,724 / 49,744 | 17,434 / 35,749 |
| Batched GEPA, cap 52 | 17,694 / 57,271 | 17,422 / 40,184 |
| Sequential GEPA, cap 52 | 17,721 / 81,537 | 17,409 / 60,951 |

The shared-miss policy changed seven backups on Llama and Mistral and three on Gemma and Flan. Compared with the original route, it spent 414 and 253 more lookups respectively and lost one pass across the two cohorts. The additional-incumbent-miss control had the same aggregate scores. The shared-miss policy saved 13.1% and 11.0% against the respective cap-52 batched GEPA controls. Its joint paired ranges against both cap-52 GEPA modes were −55 to +58 and −37 to +59. Both gates were inconclusive. The original backup order remains the default. [Per-panel results and comparison ranges](complementary-backup-results-v1.json)

## Reproduce

Use pinned GEPA 0.1.4 and a fresh output path. Two source-export replays matched byte for byte with sockets and DNS blocked, and they matched 196 published panel-control records. Three focused tests and 2,400 seeded checks covered the lookup cap, reuse of the extra probe, exact validation, critical preservation, and unchanged search when the first finalist wins. The CLI rejected a stale seal and preserved an existing report. Storage Guard measured 13.3 GiB free. The 19.6 MB scratch overlay was removed under the standing LAB exception. Fresh-model quality remains unverified. [Tests](../tests/unit/test_complementary_backup.py) · [Verification receipt](complementary-backup-verification-v1.json) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.complementary_backup \
  --execute 1c52197b9bda89466a3c69eae81506931adc5e33847a632ba26ea7eab8792a92 \
  --out NEW_REPORT.json
```
