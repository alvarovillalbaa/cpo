# Compare the start with the last qualified finalist

The paid-evidence replay produced no rollbacks. Its available pairs favored the selected prompt in every losing comparison where retaining the start would have matched GEPA. The original CPO route gives the starting prompt a separate archive comparison in the last cycle, before trying a fresh candidate. This study tests moving that comparison to the end so it can face the prompt the cycle actually selects. [Paid evidence](paid-start-retention.md) · [Original archive priority](archive-after-fresh-search.md)

The first three cycles and all final cycles without a starting-prompt archive nomination run as before. When the final archive slot belongs to the start, the variant reserves eight lookups for an additional prompt and gives fresh search a 44-lookup cap. The combined cycle ceiling stays at 68. Ordinary independent qualification chooses between the fresh nominee and incumbent. The starting prompt can then replace that provisional winner only on a strict gain on the same eight qualification cases. Both checks reuse any replies already bought on those cases.

The **after-finalist** arm always checks the provisional winner. The **fallback-only** arm checks the start only when fresh qualification fails to promote. The original preflight route, retaining the start, official sequential and batched GEPA at cap 52, and batched GEPA at cap 47 form the controls. The replay covers the existing 16 Llama and Mistral panels and 12 Gemma and Flan panels. Its gate keeps the 10% cost savings against both cap-52 GEPA modes and the nonnegative lower end of the grouped paired case range. [Runner](../benchmarks/final_start_reconciliation.py)

## Results

Each cell gives final holdout passes and paid search plus qualification lookups.

| Method | Llama and Mistral | Gemma and Flan |
| --- | ---: | ---: |
| Original preflight | 17,724 / 49,330 | 17,435 / 35,496 |
| After-finalist | 17,725 / 50,104 | 17,438 / 35,908 |
| Fallback-only | 17,729 / 50,035 | 17,442 / 35,882 |
| Batched GEPA, cap 47 | 17,687 / 45,679 | 17,407 / 31,608 |
| Batched GEPA, cap 52 | 17,694 / 57,271 | 17,422 / 40,184 |
| Sequential GEPA, cap 52 | 17,721 / 81,537 | 17,409 / 60,951 |

Both variants deferred 225 starting-prompt checks. Fresh qualification promoted a challenger in 16 of those cycles. The after-finalist check replaced three of those promotions with the starting prompt. The after-finalist arm scored eight fewer passes and paid 95 more lookups than fallback-only across the two cohorts. Fallback-only gained five passes on Llama and Mistral and seven on Gemma and Flan versus the original preflight, with 705 and 386 additional lookups. Its paired ranges against the original route were −5 to +15 and −2 to +16.

Fallback-only saved 12.6% and 10.7% relative to batched GEPA at cap 52. The joint paired ranges against both primary GEPA modes were −49 to +62 and −29 to +67, leaving both gates inconclusive. Neither variant recovered any of the 109 losing comparisons previously identified as recoverable by retaining the start. Moving the check changes fresh search opportunities in the last cycle. The result leaves the original ordering as the default. [Panel costs, counts, and paired ranges](final-start-reconciliation-results-v1.json) · [Priced loss audit](priced-gate-reachability.md)

## Reproduce

Use pinned GEPA 0.1.4 and a fresh output path. Two source-export runs matched byte for byte with sockets and DNS blocked. The replay matched 140 published panel-control records and verified the original decisions and traces on all nondeferred cycles. Three focused tests passed. The CLI rejected a stale seal and preserved an existing report. Storage Guard measured 12.8 GiB free. The 20.3 MB temporary overlay was removed under the standing LAB exception. Fresh-model quality remains unverified. [Tests](../tests/unit/test_final_start_reconciliation.py) · [Verification receipt](final-start-reconciliation-verification-v1.json) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.final_start_reconciliation \
  --execute 1c1c83305ee163ba229edbc1936947c954b0bcbe235bf2db7a091d39462e282d \
  --out NEW_REPORT.json
```
