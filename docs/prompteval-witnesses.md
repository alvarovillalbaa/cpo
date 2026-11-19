# Using incumbent validation to choose a challenger

The previous transfer test showed that a two-example training shortlist cut lookups while losing held-out passes on four panels. This follow-up tests whether spending more on ties or reusing validation observations gives a better trade-off. It uses the same candidates, search caps, official GEPA 0.1.4 controls, and subject holdouts as that comparison. [Initial transfer results](prompteval-transfer.md)

The tie-probe variant uses up to four additional training cases for the tied leaders and incumbent. It spent more than the original minibatch on all six panels and cleared both GEPA gates on the same two. Two other variants reuse shared validation observations as a shortlist screen. One uses the ordinary validation prefix. The other samples one incumbent pass and one incumbent miss when both are available.

The weighted variant measures the incumbent on the full validation set and assigns each of those two observations the size of its stratum. It selects one challenger with a higher estimated score and reuses the observations during exact validation. The challenger still needs a strictly higher fully measured score and must preserve the incumbent’s critical passes. This weighting improved aggregate exploratory accuracy by 10 passes over the original minibatch and saved 83 lookups. Each method cleared both GEPA gates on two of the six panels, with different subject and model combinations.

## Test on new subjects

The weighted selector, seeds, lookup cap, and gate were frozen before downloading recorded correctness for high-school statistics and high-school European history. The new subjects use the same two recorded models and a fixed 30% subject holdout. Each cell shows exact holdout passes and distinct lookup counts across 32 seeds. [Source dataset](https://huggingface.co/datasets/PromptEval/PromptEval_MMLU_correctness) · [Data license](../benchmarks/data/LICENSE.prompteval)

| Panel | Weighted CPO | Sequential GEPA | Batched GEPA | Cleared both GEPA gates |
| --- | ---: | ---: | ---: | --- |
| European history, Llama | 1,115 / 1,681 | 1,115 / 2,873 | 1,122 / 2,730 | No |
| European history, Mistral | 1,124 / 1,801 | 1,111 / 2,451 | 1,115 / 2,366 | Yes |
| Statistics, Llama | 1,130 / 1,761 | 1,144 / 2,907 | 1,127 / 2,820 | No |
| Statistics, Mistral | 750 / 1,685 | 768 / 2,953 | 774 / 2,772 | No |

Weighted CPO used 38% fewer lookups than sequential GEPA across the four panels and yielded 19 fewer aggregate holdout passes. It cleared both GEPA gates on one panel and remains experimental. These are recorded outcomes from new subjects, with holdout rows repeated across seeds. Model-backed development and independent live confirmation remain pending.

## Reproduce

```sh
python -m pip install --require-hashes -r requirements-benchmark.txt
python -m benchmarks.prompteval_witnesses --phase confirmation
python -m benchmarks.prompteval_witnesses --phase confirmation --execute PLAN_SHA256 --out result.json
```

Use `--phase exploratory` for the original six panels and all four new variants. Each result includes the exact source and data digests, per-panel paired decisions, and all split-level choices and scores. [Frozen design and results](prompteval-witnesses-results.json) · [Runner](../benchmarks/prompteval_witnesses.py) · [New data](../benchmarks/data/prompteval-confirmation-v1.json) · [Contract tests](../tests/test_prompteval_witnesses.py)
