# Transfer the frozen two-read CPO policy

The original bounded-discovery replay studied 18 PromptEval panels. This follow-up freezes the two-read selector, including its one-challenger shared prefix, before running it on 32 archived panels from 16 different subjects and tasks. Earlier CPO studies used these archives with different policies. The subjects are new to this selector. [Original result](prompteval-bounded-discovery.md)

One cohort contains eight PromptEval MMLU panels spanning anatomy, computer security, high school chemistry, and human aging on Llama 3 8B and Mistral 7B Instruct. The other two cohorts contain 12 panels each. They use BIG-Bench Hard and LMentry on Flan-T5-XXL and Vicuna-13B. The reduced snapshot contains binary correctness matrices and source hashes. [PromptEval dataset](https://huggingface.co/datasets/PromptEval/PromptEval_MMLU_correctness) · [BBH and LMentry response archive](https://github.com/SLAB-NLP/Multi-Prompt-LLM-Evaluation#raw-model-responses) · [Packaged outcomes](../benchmarks/data/bounded-discovery-transfer/outcomes.jsonl) · [MIT notice](../benchmarks/data/LICENSE.prompteval) · [CDLA notice](../benchmarks/data/bounded-discovery-transfer/LICENSE.cdla-permissive-2.0)

All four arms receive the same 32 seeded starts, four cycles, fixed proposal roster, 12 validation cases, 52-lookup search cap, eight independent qualification rows per cycle, and fixed 30% holdout. The controls are deferred first-gain CPO and official sequential and batched GEPA 0.1.4. The same archive nomination policy applies to each. The matched gate requires at least as many holdout passes as each GEPA control at equal or lower cost, with at least 10% savings for a score tie. The shared holdout cases recur across seeds.

## Results

Each cell reports final holdout passes and paid lookups.

| Method | MMLU | BBH and LMentry | BBH and LMentry stress | Both GEPA gates |
| --- | ---: | ---: | ---: | ---: |
| Frozen two reads | 7,730 / 26,874 | 6,354 / 46,704 | 6,879 / 44,689 | 14 / 32 |
| Deferred first-gain | 7,743 / 23,487 | 6,380 / 44,614 | 6,900 / 42,217 | 15 / 32 |
| Sequential GEPA | 7,732 / 42,163 | 6,392 / 68,275 | 6,741 / 66,854 | — |
| Batched GEPA | 7,722 / 29,566 | 6,211 / 51,641 | 6,494 / 50,177 | — |

Across the three cohorts, frozen two-read gained 98 passes and saved 33.3% of lookups against sequential GEPA. It gained 536 passes and saved 9.98% of lookups against batched GEPA. The aggregate accuracy lead against each GEPA control survived omission of any one subject or task and both of its model panels. The smallest remaining leads were 21 passes for sequential GEPA and 347 for batched GEPA. Two-read trailed sequential GEPA on MMLU and the first BBH and LMentry cohort.

Deferred first-gain scored 60 more passes than two-read and saved 7,949 lookups across the transfer. It scored more passes at lower cost in each cohort and met both GEPA gates on 15 panels. Its aggregate lead over sequential and batched GEPA was 158 and 596 passes, respectively. The transfer therefore favors deferred first-gain over the two-read extension for these archived tasks.

The data capture and each phase reproduced byte for byte in two offline runs. This is a comparison among recorded prompts and outcomes. It measures lookup cost and selection quality on the archived cohorts. A separate live evaluation is still needed for fresh prompt generation and provider costs. [Sealed panel results](bounded-discovery-transfer-results-v1.json)

Applying the same cross-cycle reuse and early qualification stopping to all four arms narrowed deferred first-gain's batched GEPA lookup lead from 16.0% to 1.95%. It met both matched gates on 10 of 32 panels under the revised accounting. [Matched-cost follow-up](bounded-transfer-matched-cost.md)

## Reproduce

Use pinned GEPA 0.1.4. Preview a phase to get its seal, then add `--execute PLAN_SHA256 --out NEW_REPORT.json`.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.bounded_discovery_transfer --phase mmlu
```

The other phases are `bbh-lmentry` and `bbh-lmentry-stress`. The packaged snapshot is sufficient for replay. To regenerate it from the three pinned source snapshots, preview `--design` and use `--capture SOURCE_DIRECTORY --execute DESIGN_SHA256 --out NEW_OUTCOMES.jsonl`. [Benchmark runner](../benchmarks/bounded_discovery_transfer.py)
