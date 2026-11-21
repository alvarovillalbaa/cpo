# Transfer of the rotating witness screen

The frozen CPO rule passed the transfer gate against batched GEPA at cap 88. It gained 41 pooled held-out passes and used 14,805 fewer lookups, a 26.4% reduction. Equal-subject accuracy increased by 0.076 percentage points and stayed positive, between 0.050 and 0.121 points, after dropping each subject in turn. [Full results](prompteval-rotating-witness-transfer-results-v1.json)

The [discovery replay](prompteval-first-proof-budget.md) found a small pooled quality edge at a lower paid cost, with a sign reversal when professional accounting was removed. This replay freezes that exact two-finalist rule and measures it on 18 other archived PromptEval panels. These cover nine subjects, each with Flan-T5 XXL and Gemma 7B IT. The selected subject–model pairs were absent from the earlier replay and from the local corpus and result records checked before capture. Some subjects appeared elsewhere with different models. [Pre-capture design](prompteval-rotating-witness-transfer-design-v1.json) · [Public source and license](https://huggingface.co/datasets/PromptEval/PromptEval_MMLU_correctness/tree/1639d5ea14c362f6964f260ae81bd903af760187)

Every panel uses 32 four-cycle episodes, 100 recorded prompt templates, and a fixed seeded 30% final holdout. In each episode all arms share the initial prompt, 12 supplied proposals per cycle, and the same train, validation, and qualification assignments. The 24 validation anchors are reused within an episode. Native GEPA receives stable case IDs across its disjoint training and validation loaders. Independent paired qualification decides promotion under the same retire-assigned case-bank rule. Paid lookups count search cache misses and the grades actually read for qualification. The replay includes cap 52 sequential and cap 80 batched GEPA as lower-cost controls, alongside their cap 88 and 136 settings and released CPO at cap 88. [Runner](../benchmarks/prompteval_rotating_witness_transfer.py)

The pre-capture gate compares CPO at cap 56 with batched GEPA at cap 88. It requires a strictly higher mean held-out accuracy across the nine equally weighted subjects, the same direction after each single-subject omission, and no increase in total paid lookups. The two model panels contribute equally within each subject. Repeated episodes use the same physical holdout cases. The omission analysis measures sensitivity to the subject mix. Proposal generation cost and fresh model behavior are outside the replay.

| Method | Search cap per cycle | Held-out passes | Paid lookups |
| --- | ---: | ---: | ---: |
| Retain initial prompt | 0 | 21,100 | 0 |
| Sequential GEPA | 52 | 21,113 | 26,600 |
| Batched GEPA | 80 | 21,167 | 39,560 |
| CPO, rotating witness with two finalists | 56 | 21,257 | 41,359 |
| Batched GEPA, primary control | 88 | 21,216 | 56,164 |
| Sequential GEPA | 88 | 21,332 | 107,981 |
| Batched GEPA | 136 | 21,354 | 125,720 |
| Sequential GEPA | 136 | 21,357 | 133,028 |
| Released CPO | 88 | 21,468 | 158,840 |

Relative to the primary control, the witness rule was cheaper on all nine subjects and improved ten panels, tied five, and regressed on three. The largest subject-level accuracy decline was 0.289 percentage points in professional medicine. Batched GEPA at cap 80 used 1,799 fewer lookups than the witness rule and scored 90 fewer passes. Wider GEPA settings and released CPO achieved higher accuracy at higher cost. The rule adds an observed low-cost operating point with this supplied prompt stream.

CPO exposes this selector through an opt-in cycle with independent paired qualification and budgeted critical-row checks. [Package API and trace verification](rotating-witness-cycle.md)

## Reproduce

Use Python 3.12 and the hash-pinned GEPA wheel. The capture recorded the dataset repository revision before and after fetching, ordered binary labels, viewer response hashes and source URLs. A separate replay seal binds the exact captured snapshot to the pre-capture design. Storage Guard measured 9.2 GiB free. The standing LAB storage exception covered a disposable source and wheel overlay bounded at 0.2 GiB. The capture read 8.6 MB of public labels and retained 550,443 bytes. The replay ran with DNS and outbound socket calls blocked. [Captured corpus](../benchmarks/data/prompteval-rotating-witness-transfer-v1.json) · [Benchmark wheel](../requirements-benchmark.txt) · [Gate tests](../tests/unit/test_prompteval_rotating_witness_transfer.py)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.prompteval_rotating_witness_transfer --execution-plan
PYTHONHASHSEED=0 python -B -m benchmarks.prompteval_rotating_witness_transfer \
  --execute a3b656d7b5dc053d8b73320416e1ce11e03fcde4d84b0a12e062379f4d80b37d \
  --out NEW_REPORT.json
```

The receipt SHA-256 is `e234c20ec178745ca55ff2e01aabf9f75e69377997690302fc615d7d8b6cc5ac`.
