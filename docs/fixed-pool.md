# Fixed-pool comparison

CPO 0.4.0 adds a selector for a finite set of prompts. It evaluates the incumbent on the full validation set and abandons a challenger when the remaining rows cannot raise its exact score above the current leader’s. The optional screen ranks candidates on a common prefix. The optional shortlist limits how many screened candidates receive a full challenge. A partial validation result cannot displace the incumbent.

The opt-in `adaptive_rejection=True` setting uses paid screen outcomes and skips unaffordable challenges. Its lookup order reduced validation cost across 18 recorded panels while preserving all selections under a fully funded four-challenger schedule. [Adaptive rejection](prompteval-rejection.md)

For tasks with declared critical strata, the coverage-first selector can abandon an impossible coverage check before completing the validation panel. [Coverage-aware fixed-pool API and qualification example](covered-pool.md)

The rotating-witness cycle can screen a supplied roster with a few shared cases before sending a single challenger to independent paired qualification. [Rotating-witness API and verification](rotating-witness-cycle.md)

The paired opening cycle tries a supplied rewrite and repair in order and can certify the first exact validation gain from partial paired evidence. [Paired opening API and transfer results](paired-opening-cycle.md)

## Protocol

The replay uses recorded correctness matrices for Llama 3 8B on PromptEval’s abstract algebra subset and for candidate pools published with GEPA on AIME and ARC-AGI. Each phase uses 40 seeded splits per dataset, partitions validation and held-out rows, and caps search at 55% of the full validation grid. All arms see the same pool and validation order within each split. The gates require preserved aggregate held-out correctness and no added lookups, with either an accuracy gain or at least 10% savings. [PromptEval paper](https://arxiv.org/abs/2405.17202) · [PromptEval dataset](https://huggingface.co/datasets/PromptEval/PromptEval_MMLU_correctness) · [GEPA artifact](https://github.com/gepa-ai/gepa)

Uniform selection gives each candidate the same validation prefix. The shared-prefix Successive Halving adapter extends that prefix for surviving candidates and drops roughly half at each stage. It may choose a partial-validation finalist. The CPO arms compare exact racing, common-prefix screening followed by racing, and screening followed by one fully validated challenge. [Successive Halving paper](https://proceedings.mlr.press/v51/jamieson16.html)

## Results

Exact racing cleared both external controls on ARC-AGI in phase one and missed the gate on the other two datasets. Screening the whole pool missed the combined gate in phase two. In phase three, the one-challenger shortlist produced the following matched results.

| Dataset | Shortlist passes / lookups | Uniform passes / lookups | Halving passes / lookups | Shortlist passes both gates |
| --- | ---: | ---: | ---: | --- |
| Abstract algebra | 914 / 4,520 | 917 / 6,760 | 932 / 5,320 | No |
| AIME | 703 / 1,293 | 696 / 1,800 | 689 / 1,520 | Yes |
| ARC-AGI | 2,156 / 1,913 | 2,166 / 2,800 | 2,144 / 2,200 | No |

The shortlist also lost seven passes against exact CPO racing on AIME. The results support keeping these policies opt-in. New phases use different seeds over the same recorded matrices, so their holdouts overlap across trials. This test measures selection under a lookup cap. It excludes new proposal generation, provider cost, and end-to-end optimizer comparisons. [Exact totals, paired results, and digests](fixed-pool-results.json)

## Reproduce

Provide the recorded correctness matrix from the research archive. The CLI validates its dimensions, hashes the input, and previews the plan before executing. Use commit `e4b5ee12354c376fb2c696f09b0e04a566696c69` for the exact phase-one and phase-two plan digests.

```sh
python -m benchmarks.pool --dataset aime --matrix MATRIX_PATH --phase 3
python -m benchmarks.pool --dataset aime --matrix MATRIX_PATH --phase 3 --execute PLAN_SHA256 --out result.json
```
