# Confirm posterior allocation on new archived model panels

The prior posterior-wide policy saved lookups against both GEPA controls on archived MMLU trajectories. Its joint paired accuracy range included zero. This experiment keeps the existing policy and tests it on model-by-subject panels absent from the local CPO snapshots. [Prior result](routed-score-allocation.md)

The six subjects are high-school geography, government and politics, microeconomics, statistics, moral disputes, and world religions. The model splits are Gemma 7B base and Flan-T5 XXL. Some subjects appeared with other models in previous replays. The trial tests transfer to new recorded prompt outcomes for these model-subject combinations. Its frozen input objects come from the MIT-licensed PromptEval correctness archive. [Source archive](https://huggingface.co/datasets/PromptEval/PromptEval_MMLU_correctness) · [License](../benchmarks/data/LICENSE.prompteval)

The three CPO arms use the same 32 seeded four-cycle episodes, case partitions, and independent eight-case qualification. The candidate uses posterior allocation when the original route widens. The exact-wide arm uses an exact race at the same trigger. Official sequential and batched GEPA use the same 52-lookup search limit, and a secondary batched control uses cap 47. Retaining the starting prompt is a zero-lookup control.

The primary gate requires at least 10% lookup savings against both cap-52 GEPA modes and a nonnegative lower endpoint for the joint central 95% paired range. Draws resample original holdout cases within subject and keep both models and all 32 episodes together. The complete design and source object identities are frozen before retrieving correctness rows. [Frozen design](posterior-model-transfer-design-v1.json) · [Runner](../benchmarks/posterior_model_transfer.py)

## Results

| Method | Holdout passes / 25,920 | Paid lookups |
| --- | ---: | ---: |
| Retain start | 17,404 | 0 |
| Original route | 17,435 | 35,496 |
| Exact race when wide | 17,438 | 36,527 |
| Posterior allocation when wide | 17,434 | 36,665 |
| Batched GEPA, cap 47 | 17,407 | 31,608 |
| Batched GEPA, cap 52 | 17,422 | 40,184 |
| Sequential GEPA, cap 52 | 17,409 | 60,951 |

Posterior allocation failed the gate. It saved 39.8% of paid lookups against sequential GEPA and 8.8% against batched GEPA at cap 52. The joint paired range was −36 to +58 passes across resamples of 405 holdout cases. The original route had one more pass and used 1,169 fewer lookups. The batched cap-47 control had 27 fewer passes and used 5,057 fewer lookups. The paired range for posterior allocation against that cheaper control was −20 to +75 passes. These comparisons use recorded outcomes for fixed prompt pools. Fresh-model performance remains unverified. [Machine-readable results](posterior-model-transfer-results-v1.json)

## Reproduce

Use GEPA 0.1.4 and the bundled snapshot. The results and capture receipt identify the exact design commit and source hashes. Two replays produced identical bytes with socket connections and DNS disabled. The runner rejected a stale capture seal and refused to overwrite a result. Capture used a hash-verified DuckDB 1.4.3 wheel in a temporary environment. [Snapshot](../benchmarks/data/posterior-model-transfer-v1.json) · [Verification receipt](posterior-model-transfer-verification-v1.json)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.posterior_model_transfer \
  --replay benchmarks/data/posterior-model-transfer-v1.json \
  --execute 5853133381f0f44e58c057f696b61475869c2887e40a7c01404010a8f9f24538 \
  --out NEW_REPORT.json
```
