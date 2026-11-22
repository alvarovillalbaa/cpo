# Test the cap-13 CPO policy on disjoint MMLU subjects

The original cap sweep selected a strict validation race capped at 13 search lookups on MMLU. This replay freezes that policy and tests it on 14 different subjects and four different model checkpoints, using all 28 panels from the existing transfer archive. The 896 seeded trials share 672 distinct held-out cases. Starts, rosters, and disjoint validation and qualification keep the archived schedule. The original cap and target identities were fixed before this replay scored the target. [Cap selection](recorded-validation-tail-matched-caps.md) · [Target archive](recorded-two-witness-mmlu-transfer.md)

The gate requires a positive observed margin and a nonnegative lower paired range against the best affordable common GEPA setting or the retained starts. The two native modes sweep all integer search caps from 6 through 180. Affordability includes search and qualification lookups. Each paired draw keeps both model panels and all repeated seeds for each case together and reselects the control at the same realized budget.

| Setting | Held-out passes | Lookups |
| --- | ---: | ---: |
| Retain the starts | 26,625 | 0 |
| Best affordable fixed native setting, sequential cap 16 | 26,623 | 9,572 |
| Frozen CPO cap 13 | 26,610 | 9,596 |
| GEPA with separate settings per subject, chosen with hindsight | 26,652 | 9,062 |
| Full-pool CPO cap 54, for attribution | 26,664 | 22,503 |

Cap 13 missed the transfer gate. Retaining the starts ranked first among the affordable controls. The paired CPO margin was **−15 passes**, with a 95% range of **−41 to +8**. The subject-specific GEPA schedule used held-out grades to set the caps and describes this archive. [Full results and per-panel receipts](recorded-low-cap-mmlu-transfer-results-v1.json)

## What the smaller cap skipped

Cap 13 promoted 32 times. The full-pool race promoted 72 times and gained 54 passes over cap 13. Both arms had to prove a strict validation gain and qualify the same nominee independently.

| Deployment outcome | Trials | Full-pool pass gain | Extra full-pool lookups |
| --- | ---: | ---: | ---: |
| Same prompt deployed | 842 | 0 | 11,600 |
| Cap 13 retained, full pool promoted | 45 | +42 | 1,099 |
| Cap 13 promoted, full pool retained | 5 | +9 | 123 |
| Both promoted different prompts | 4 | +3 | 85 |

The 45 extra promotions supplied most of the full-pool gain. About 90% of the extra cost fell in trials whose deployment stayed the same. This comparison observes the outcome after both paths ran. The candidate's fresh-model performance remains unverified. [Replay runner](../benchmarks/recorded_low_cap_mmlu_transfer.py)

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel.

Two clean-export replays with DNS and sockets blocked matched byte for byte at SHA-256 `35da1bc739556d0743975c20780d5775ca39745bfe27f6214a967f693e414a73`. Fifteen targeted tests passed. Direct runs verified the GEPA cap-16 point, the subject-specific GEPA schedule, and cap-54 versus cap-180 CPO parity across all 896 trials. The final seal adds per-deployment cost attribution and preserves the first run’s decisions, scores, and paired case vectors. The CLI rejected the preceding seal. Storage Guard measured 2.7 GiB free. The export and publication worktree fit the standing 0.2 GiB LAB exception. The replays sent zero provider requests. [Targeted tests](../tests/unit/test_recorded_low_cap_mmlu_transfer.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.recorded_low_cap_mmlu_transfer
python -B -m benchmarks.recorded_low_cap_mmlu_transfer \
  --execute 0a14b82b3ccc96865fba2d572ad1bb9b3228d61232583983130b6229c9388037 \
  --out NEW_REPORT.json
```
