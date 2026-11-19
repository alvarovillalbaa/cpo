# Replicate the low-budget CPO comparison on 12 new panels

The earlier replay found a large lookup saving for seeded CPO at cap 28 and an uncertain accuracy difference against sequential GEPA at cap 31. This replication froze those two settings, the secondary controls, the case split, and the gate before downloading the new score tables. The design commit is `9f7f1107f04339c69fac591bdb3e94952de3e463`. [Earlier audit](independent-mmlu-cost-uncertainty.md) · [Frozen design](low-budget-transfer-design-v1.json)

The new subjects are clinical knowledge, college physics, electrical engineering, high school biology, moral scenarios, and professional medicine. Both the Flan-UL2 and Mixtral 8×7B Instruct model splits were absent from the prior local archive snapshots. Each of the 12 new panels contains 100 prompt templates. The capture verified the public dataset revision before and after downloading the score tables and retained binary outcomes, SHA-256 hashes of the source responses, and case-order hashes. [PromptEval dataset](https://huggingface.co/datasets/PromptEval/PromptEval_MMLU_correctness) · [MIT notice](../benchmarks/data/LICENSE.prompteval) · [Captured scores](../benchmarks/data/low-budget-transfer-v1.json)

Each panel has 32 seeded four-cycle episodes with the same starting prompts, proposal rosters, recency archive, 12 validation cases, and eight independent qualification cases per cycle. The holdout contains 594 distinct cases and 38,016 repeated decisions. Each of 4,096 draws resamples case IDs within a subject and keeps both models and all episodes together. The primary comparison requires at least a 10% measured lookup saving and a central 95% range with a lower endpoint of zero or higher. A range spanning zero gives an inconclusive result when the cost condition passes. [Runner](../benchmarks/low_budget_transfer.py)

## Results

| Setting | Holdout passes / 38,016 | Paid lookups |
| --- | ---: | ---: |
| Retain starting prompt | 18,799 | 0 |
| Seeded CPO, cap 28 | 18,813 | 19,602 |
| Seeded CPO, cap 52 | 18,842 | 31,705 |
| Sequential GEPA, cap 31 | 18,815 | 28,822 |
| Batched GEPA, cap 39 | 18,801 | 17,563 |
| Batched GEPA, cap 44 | 18,866 | 30,649 |

Against the fixed primary GEPA control, cap-28 CPO saved **9,220 lookups, or 32.0%**, and scored two fewer passes. The central 95% paired range was **−56 to +53 passes**. CPO used fewer lookups on all six subjects and scored more passes on three. Omitting one subject at a time moved the aggregate difference between −9 and +5. The frozen gate returned **inconclusive**.

Cap-28 CPO gained 12 passes against batched GEPA at cap 39 and spent 2,039 more lookups. Batched GEPA at cap 44 used 1,056 fewer lookups than cap-52 CPO and gained 24 passes. The primary cost saving replicated against the fixed sequential setting. A general accuracy advantage remains unverified, and no optimizer default changed. [Sealed panel and resample results](low-budget-transfer-results-v1.json)

Two offline executions produced byte-identical reports. These are new-to-the-project archived subjects and model splits with fixed prompt templates. The resampling range is conditional on those subjects and trajectories. Fresh-prompt quality and live provider costs remain unverified.

## Reproduce

Use GEPA 0.1.4 for offline replay. The packaged correctness snapshot supplies all inputs.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.low_budget_transfer --design
PYTHONHASHSEED=0 python -B -m benchmarks.low_budget_transfer \
  --replay benchmarks/data/low-budget-transfer-v1.json \
  --execute e2563eab817dcafef3140a40c890ea07b9927d49e7e6379970d61b8da0c267e3 \
  --out NEW_REPORT.json
```
