# Compare frozen CPO and GEPA on new archived subjects and models

This replay tests the seeded CPO default and the fresh-first archive variant on archived panels outside the earlier CPO captures. The design fixed four subjects, both models, five methods, the schedules, the budget, and the decision gate before any of the eight correctness tables were downloaded. The design commit is `5a960958f86baf7fc3f2fcb4c7118b7001f95506`. [Pre-capture design](independent-mmlu-transfer-design-v1.json) · [Prior archive comparison](archive-after-fresh-search.md)

The subjects are college biology, machine learning, nutrition, and security studies. Each panel contains all 100 templates on either Gemma 7B IT or Falcon 40B. There are 144, 112, 306, and 245 cases per model in the respective subjects. The capture checked the original dataset revision before and after reading the eight public viewer tables. It retained binary correctness, case order hashes, and SHA-256 hashes of the viewer responses. Both model panels for each subject share the same ordered case IDs. [PromptEval dataset](https://huggingface.co/datasets/PromptEval/PromptEval_MMLU_correctness) · [MIT notice](../benchmarks/data/LICENSE.prompteval) · [Captured matrices](../benchmarks/data/independent-mmlu-transfer-v1.json)

Each panel uses 32 seeded four-cycle episodes with a common start, fixed proposal blocks, 12 validation rows per cycle, a 52-lookup search ceiling, and eight separate qualification rows per cycle. Episodes reuse a fixed 30% holdout per subject. Both official GEPA 0.1.4 controls can reinvest cache hits within the paid cap. The retain-start arm reads only the final holdout. A CPO method clears a panel's gate if it matches or exceeds each GEPA control's passes at equal or lower paid cost and gains a pass or saves at least 10% at equal accuracy. [Benchmark runner](../benchmarks/independent_mmlu_transfer.py) · [GEPA accounting](gepa-paid-cap-transfer.md)

## Results

| Method | Holdout passes / 15,360 | Mean panel accuracy | Paid lookups | Panels clearing both GEPA gates / 8 |
| --- | ---: | ---: | ---: | ---: |
| Retain starting prompt | 8,918 | 55.433% | 0 | — |
| CPO, seeded preflight | 8,971 | 55.836% | 21,477 | 2 |
| CPO, seeded fresh-first | 8,965 | 55.817% | 22,213 | 2 |
| GEPA sequential | 8,992 | 55.904% | 42,609 | — |
| GEPA batched | 8,996 | 55.994% | 29,285 | — |

Seeded preflight gained 53 passes over retaining the starting prompt. It finished 25 passes below batched GEPA while using 26.7% fewer paid lookups. Both CPO arms cleared both GEPA gates on Falcon college biology and Gemma security studies. Fresh-first used 736 additional lookups and lost six passes against preflight. Seeded preflight remains the default.

Nutrition accounted for 21 of the 25 passes lost to batched GEPA. Falcon nutrition is the largest single panel deficit. The default scored 1,850 passes, compared with 1,863 for retaining the start and 1,867 for batched GEPA. Omitting nutrition and both its model panels leaves a four-pass deficit against batched GEPA. Giving each panel equal weight still leaves the default 0.158 percentage points below batched GEPA.

These are newly captured panels of archived, supplied prompt templates. They test transfer to subjects and models outside the prior CPO experiments. The within-subject seeds share holdout cases. Fresh-prompt superiority and provider cost remain unverified. Two socket-blocked replays produced byte-identical reports from the frozen capture. [Full panel scores, gates, and hashes](independent-mmlu-transfer-results-v1.json)

## Reproduce

Use GEPA 0.1.4 for offline replay. The design preview reproduces the pre-capture seal. The capture command reads public correctness data when used with `--capture --execute DESIGN_SHA256 --out NEW_CORPUS.json`. The packaged snapshot is sufficient for replay.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.independent_mmlu_transfer --design
PYTHONHASHSEED=0 python -B -m benchmarks.independent_mmlu_transfer \
  --replay benchmarks/data/independent-mmlu-transfer-v1.json \
  --execute 9c0a73dbd7114183be1857a05850deb94a3d8800ebadebf6382e65a934e0583c \
  --out NEW_REPORT.json
```
