# Rerank CPO nominees using already-paid validation

The MMLU gap audit showed that an alternative nominee can sometimes pass the same independent admission within the existing lookup allowance. This replay tests three ways to choose an already-evaluated prompt. It holds the witness and fallback search prefix fixed. When the original path reaches its first nomination, the replay chooses among the enrolled challengers with a paid grade. Each arm submits one proof on the selected prompt's original admission panel and can extend a tie under the existing reserve rule. Episodes without a nomination retain the starting prompt. [MMLU gap audit](witness-mmlu-gap.md) · [Runner](../benchmarks/witness_paid_nominee_ranking.py)

| Rule | Ranking signal |
| --- | --- |
| Smoothed pass rate | Paid passes with a prior of one pass and one fail |
| Paired margin | Paid gains minus losses on cases shared with the incumbent, divided by the number of pairs plus two |
| Case-adjusted | Total excess passes over other prompts' smoothed rate on the same cases, divided by the candidate's read count plus two |

Every rule preserves the original nominee on ties. It reads the paid ledger before opening any admission or holdout replies. The proof allowance is the original worst-case limit for one proof, including its tie extension. The audit charges the full original search prefix and the exact proof replies of each policy.

BBH and LMentry admission outcomes choose a rule for both MMLU cohorts. MMLU admission outcomes choose a rule for BBH and LMentry. Selection maximizes promotions among rules within the original realized proof spend on the training family, with lower cost as the first tie-break. The transfer gate requires an out-of-family positive paired lower endpoint against original CPO and at most its realized paid lookups on each cohort. The comparison also rematches the strongest recorded native GEPA point at each policy's observed cost. Holdout results never choose the transferred rule.

## Results

Both training families retained the original rule under the proof budget, so neither transfer qualified. The individual rules produced the following recorded holdout pass and lookup totals. [Sealed results, native points, and paired ranges](witness-paid-nominee-ranking-results-v1.json)

| Cohort | Original | Smoothed pass rate | Paired margin | Case-adjusted |
| --- | ---: | ---: | ---: | ---: |
| BBH and LMentry | 17,068 / 72,534 | 17,095 / 72,538 | 17,073 / 72,537 | 17,095 / 72,550 |
| MMLU prior subjects | 21,180 / 34,343 | 21,180 / 34,343 | 21,180 / 34,343 | 21,180 / 34,343 |
| MMLU additional subjects | 8,976 / 13,754 | 8,976 / 13,754 | 8,976 / 13,754 | 8,976 / 13,755 |

On BBH and LMentry, smoothing gained 27 passes and spent four additional lookups. Its paired 95% range was −0.005 to +0.149 percentage points. Case adjustment gained the same number of passes and spent 16 more lookups. The original rule admitted 755 of 1,242 nominees there and 134 of 539 on MMLU. Across the 539 MMLU nominations the rules changed the nominee only once. That switch used one extra proof lookup and preserved the aggregate holdout score. The paid grades supported few alternative selections under these rules. The earlier hindsight ceiling includes alternatives whose independent proof and holdout outcomes the ranking cannot see. [Hindsight menu and limits](witness-mmlu-gap.md)

A matched probe changed 32 MMLU nominations. It spent more under the original allowance and produced no pooled holdout gain. [Probe versus same-cap proof controls](witness-nominee-probe.md)

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel from a clean source export. Fourteen targeted tests passed, and two full offline replays produced byte-identical results. The original live plan and all original archived cohort costs and scores reproduced. Storage Guard measured 5.8 GiB free. The task-owned export and wheel overlay fit within the standing 0.2 GiB LAB exception and were removed. [Tests](../tests/unit/test_witness_paid_nominee_ranking.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.witness_paid_nominee_ranking
python -B -m benchmarks.witness_paid_nominee_ranking \
  --execute 501cd7663898409c3d6d88386424f9dc18a7eb41754b34f468522a627741e1e3 \
  --out NEW_REPORT.json
```
