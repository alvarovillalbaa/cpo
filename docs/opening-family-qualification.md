# Use validation-guided repair with exact family qualification

The opt-in cycle stages up to three edits before full validation. After an edit, it checks the opening’s previous validation misses to find training rows for the next proposal. It preserves a full validation reserve. A chain becomes the nominee only after a strict gain with every protected critical pass and family score preserved. The final nominee faces independent paired qualification against the starting prompt. [Repair API](../cpo/validation_guided_repair.py)

```python
from cpo import ProposalPair
from cpo.validation_guided_repair import run_validation_guided_repair_cycle

result = run_validation_guided_repair_cycle(
    incumbent,
    train,
    validation,
    holdout,
    evaluate,
    propose,
    input_features=lambda row: features_by_id[row.id],
    opening_pair=ProposalPair(rewrite, repair),
    metric_limit=56,
    qualify=qualify,
)

next_incumbent = result.prompt
```

`input_features` supplies input-only categorical strings, integers, or booleans on training and validation rows. `diagnostic_prompt` can transform the current prompt for training probes, while the proposer receives the full parent and measured training observations. `metric_limit` covers search lookups. `qualification_limit` separately caps qualification. Count the supplied opening’s proposal cost separately.

The cycle uses `certify_family_qualification`. The certificate prioritizes unresolved critical pairs, then families that still need favorable observations to prove nonregression. Estimates from observed replies choose which prompt to read next. Exact bounds determine when a strict gain and every family and critical constraint are settled. The certificate also works as a standalone function. [Qualification API](../cpo/family_qualification.py)

## Fresh scripted comparison

CPO and both GEPA controls used the same adaptive qualification schedule. The benchmark also ran each method with seeded paired ordering and checked every selected prompt, holdout decision, and search count for equality. It reproduced the prior seeded report. The new cohort consists of 36 disjoint input panels, scored with the original faults and with independently shifted fault locations. Each table cell gives exact holdout passes out of 648 and total counted calls.

| Method | Original faults | Shifted faults |
| --- | ---: | ---: |
| Validation-guided CPO | 648 / 2,239 | 646 / 2,269 |
| Sequential GEPA | 562 / 2,455 | 558 / 2,503 |
| Batched GEPA | 526 / 2,276 | 515 / 2,276 |

The shared schedule closed the batched cost gap in both modes. CPO cleared three of four GEPA gates. With shifted faults it lost two matched critical cases against sequential GEPA, both on `archive/overlap/64997`. The cycle found a residual validation miss but all four routed training probes passed. It qualified the partially repaired draft and finished with 15 search lookups available. The full confirmation gate failed. The API remains opt-in and live evidence remains pending. [Sealed results](opening-family-qualification-results-v1.json)

## Reproduce offline

Use GEPA 0.1.4 and a fresh output path.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.opening_family_qualification
PYTHONHASHSEED=0 python -B -m benchmarks.opening_family_qualification \
  --execute b237ed41a0907da0c1665095e0803c9b55ae8d74bdc61fc1d62d175102326e01 \
  --out NEW_REPORT.json
```

Two clean source replays and an installed-wheel replay matched byte for byte with sockets and DNS blocked. Each replay covered 72 input panels across 144 panel and mode combinations, with 576 native GEPA paths across the two qualification schedules. The API matched the benchmark prototype’s complete request traces. All 23 focused tests passed in each environment, including an exhaustive comparison against the full paired rule on 4,096 two-repeat outcome patterns. The runner rejected an altered seal and preserved an existing report. Storage Guard measured 4.7 GiB free and the scratch exports were removed under the standing LAB exception. [Verification receipt](opening-family-qualification-verification-v1.json)
