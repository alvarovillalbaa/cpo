# Adaptive rejection in exact prompt-pool selection

`select_pool(..., adaptive_rejection=True)` uses the observations already collected during validation to spend fewer lookups on losing or unaffordable challengers. Screening and candidate ordering follow the existing settings. The selector first checks whether the paid observations already rule out a challenger. It skips a challenge when its remaining validation cannot fit in the budget. It visits unmeasured protected cases first, then checks cases with lower observed pass rates across the candidates already evaluated.

A challenger still needs a complete exact validation score, a strict improvement over the current leader, and every critical pass protected by the original incumbent. Row difficulty affects lookup order only. When the budget can cover every shortlisted candidate, both lookup orders select the same prompt on fixed outcomes. A tighter cap can fund different complete challenges.

## Recorded outcomes

The replay used 576 splits across 18 PromptEval model and subject panels. It reused the same recorded rows, templates, and split seeds as the earlier studies. The official GEPA arms reproduced their earlier selections and lookup counts. [PromptEval data and source](prompteval-transfer.md) · [Panel results](prompteval-rejection-results-v2.json)

| Candidate schedule | Fixed order passes / lookups | Adaptive rejection passes / lookups | Changed selections |
| --- | ---: | ---: | ---: |
| First four challengers, cap 171 | 18,863 / 45,173 | 18,863 / 43,269 | 0 |
| Four challengers after a shared screen, cap 171 | 18,863 / 67,528 | 18,863 / 66,059 | 0 |
| Entire candidate pool, cap 171 | 18,899 / 83,228 | 18,911 / 76,153 | 25 |
| First four challengers, cap 72 | 18,881 / 38,304 | 18,879 / 32,719 | 4 |

With four fully funded challengers and no screen, adaptive rejection preserved every selected prompt and saved 1,904 lookups across the 18 panels. With the tight cap, it used 14.6% fewer lookups and lost two aggregate passes. The full-pool race added 12 passes and saved 8.5% of its lookups, while still missing the combined GEPA gate on all 18 panels. The ordered four-challenger variant cleared both GEPA controls on three panels. These results support the opt-in setting for reducing exact validation work. Fresh end-to-end model performance remains unmeasured.

## Reproduce

```sh
python -m pip install --require-hashes -r requirements-benchmark.txt
python -m benchmarks.prompteval_rejection --phase different-subjects
python -m benchmarks.prompteval_rejection --phase different-subjects --execute PLAN_SHA256 --out result.json
```

Use `--phase development` for the original six panels or `--phase prior-confirmation` for European history and statistics. The runner checks exact selected scores and complete validation receipts. Unit tests exercise the critical-pass rule, cached rejection, and the affordability check. [Selector](../cpo/pool.py) · [Runner](../benchmarks/prompteval_rejection.py) · [Contract tests](../tests/test_pool.py)
