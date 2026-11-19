# Recorded transfer to three PromptEval subjects

This test transfers CPO’s precomputed opening and fixed-pool selectors to six recorded model panels. The panels cover formal logic, high-school computer science, and world religions for Llama 3 8B and Mistral 7B Instruct v0.2. Each panel contains 100 prompt templates and the complete ordered binary correctness vectors. The bundled snapshot records the observed Hugging Face revision, source URLs, and raw response hashes. It contains correctness labels only. [Dataset](https://huggingface.co/datasets/PromptEval/PromptEval_MMLU_correctness) · [PromptEval paper](https://arxiv.org/abs/2405.17202) · [Upstream notice](../benchmarks/data/LICENSE.prompteval)

The protocol fixes a common 30% holdout per subject before any search and keeps those rows out of training and validation on all 32 seeds. Each seed supplies all methods with the same 13 templates, 12 training cases, 24 validation cases, and 171-lookups ceiling. CPO’s precomputed branch sees the first two alternatives in the fixed stream. Official GEPA 0.1.4 uses the same stream through sequential and batched proposal adapters. The pooled controls use uniform, Successive Halving, CPO exact racing, or certified early selection.

After the initial CPO result missed the GEPA gate, the comparison added a minibatch shortlist on the same panels. It scores all 13 templates on two shared training examples, then submits one challenger for full CPO validation only if it beats the incumbent on that minibatch. Its full-validation promotion rule stays in place. This is an exploratory ablation on the transfer panels.

## Results

Each cell shows aggregate exact holdout passes and distinct search lookups.

| Panel | Precomputed CPO | Minibatch CPO | Sequential GEPA | Batched GEPA |
| --- | ---: | ---: | ---: | ---: |
| Formal logic, Llama | 472 / 5,214 | 474 / 1,808 | 481 / 2,939 | 475 / 3,052 |
| Formal logic, Mistral | 386 / 5,126 | 382 / 1,701 | 379 / 2,527 | 380 / 2,346 |
| Computer science, Llama | 593 / 5,112 | 589 / 1,713 | 585 / 2,419 | 589 / 2,460 |
| Computer science, Mistral | 566 / 4,996 | 564 / 1,750 | 568 / 2,604 | 563 / 2,600 |
| World religions, Llama | 1,256 / 4,168 | 1,254 / 1,632 | 1,259 / 2,433 | 1,256 / 2,390 |
| World religions, Mistral | 1,177 / 4,395 | 1,198 / 1,643 | 1,203 / 2,240 | 1,201 / 2,184 |

The gate requires preserved holdout totals and lookup cost, with either more exact passes or at least 10% fewer lookups. Precomputed CPO missed the gate against both GEPA controls on all six panels. Minibatch CPO used fewer lookups on every panel, cleared both GEPA controls on two panels, and retained a holdout deficit against at least one control on the other four. It remains a benchmark variant.

The test measures search on public, fixed outcomes. Each subject’s holdout rows recur across seeds, and the source supplies templates in advance. The replay leaves fresh proposal quality and provider cost unmeasured.

The follow-up compared extra probes on tied candidates with two ways of reusing validation probes. It then froze the best exploratory trade-off before loading four new recorded panels. [Validation witness comparison](prompteval-witnesses.md)

A separate follow-up tested whether a second model's training outcomes could rank templates for the target model on four new subjects. [Second-model screening](prompteval-proxy.md)

## Reproduce

```sh
python -m pip install --require-hashes -r requirements-benchmark.txt
python -m benchmarks.prompteval_transfer
python -m benchmarks.prompteval_transfer --execute PLAN_SHA256 --out transfer-result.json
```

Preview prints the seal, subject holdout IDs, and source digests. The report includes all eight methods, selections, counts, and paired outcomes for every seed. A clean export reproduced the report with sockets blocked. [Measured totals and hashes](prompteval-transfer-results.json) · [Runner](../benchmarks/prompteval_transfer.py) · [Data](../benchmarks/data/prompteval-transfer-v1.json) · [Tests](../tests/test_prompteval_transfer.py)
