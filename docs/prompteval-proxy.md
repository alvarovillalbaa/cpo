# Screening prompt candidates on a second model

This replay tests whether recorded outcomes from a second model can cheaply rank candidate templates for the target model. It pairs the same numbered template and example positions across Llama 3 8B and Mistral 7B Instruct v0.2. Both model directions ran on business ethics, high-school geography, high-school mathematics, and prehistory. These four subjects were frozen before the correctness tables were retrieved. [PromptEval data card](https://huggingface.co/datasets/PromptEval/PromptEval_MMLU_correctness) · [Publisher's matrix extraction](https://github.com/felipemaiapolo/prompteval/blob/main/prompteval/create_data.py#L28-L40)

Each panel runs 32 candidate pools with 13 templates, the same training and validation sizes as the previous transfer study, and a fixed 30% holdout. Proxy CPO ranks the 12 challengers by correctness on two training cases. It sends only the top two to exact target-model validation. The incumbent keeps its place unless a challenger achieves a strict validation gain. The controls include ranking on the target model, taking the first two challengers in the preseeded order, the original CPO minibatch, and official GEPA 0.1.4 in sequential and batched modes. Every arm has a cap of 171 distinct model, template, and case lookups per split.

## Results

The primary analysis charges one quarter of a target lookup for every proxy lookup. These rates test cost sensitivity. No provider spend was measured.

| Method | Held-out passes | Target lookups | Proxy lookups | Cost in target lookup units |
| --- | ---: | ---: | ---: | ---: |
| Proxy screen, two cases | 10,257 | 13,872 | 6,144 | 15,408 |
| Proxy screen, four cases | 10,227 | 13,901 | 12,288 | 16,973 |
| Target screen, two cases | 10,272 | 20,101 | 0 | 20,101 |
| First two challengers in seeded order | 10,271 | 13,848 | 0 | 13,848 |
| Original CPO minibatch | 10,241 | 13,684 | 0 | 13,684 |
| Sequential GEPA | 10,264 | 21,276 | 0 | 21,276 |
| Batched GEPA | 10,284 | 20,808 | 0 | 20,808 |

The two-case proxy screen cleared both GEPA gates on the two geography panels and missed their combined gate on the other six panels. It cleared the gate against the matched target screen on three panels and against the seeded-order control on zero. Across all eight panels it lost 14 held-out passes and used about 11% more cost units than selecting the first two challengers. The two-case proxy incurred 24 more target lookups even before charging for screening. Four proxy cases added work and reduced aggregate accuracy further. The relative model-price scenarios and per-panel outcomes are retained in the report. [Seals and panel results](prompteval-proxy-results-v1.json)

This is a test of template selection on recorded outputs. It supports keeping second-model screening out of the default search path. Transfer to fresh model replies and newly generated prompts remains unmeasured.

## Reproduce

```sh
python -m pip install --require-hashes -r requirements-benchmark.txt
python -m benchmarks.prompteval_proxy --design
python -m benchmarks.prompteval_proxy
python -m benchmarks.prompteval_proxy --execute PLAN_SHA256 --out result.json
```

The plan binds the original design, the captured dataset revision and file hash, the holdout IDs, and the runner and comparator sources. The result records the selected prompts by template index, both lookup counts, and an ordered search digest for every split. [Runner](../benchmarks/prompteval_proxy.py) · [Captured data](../benchmarks/data/prompteval-proxy-v1.json) · [Data license](../benchmarks/data/LICENSE.prompteval)
