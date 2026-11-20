# Confirm late miss substitution on unused archived model and subject pairs

Late miss substitution improved both observed CPO point scores on its development cohorts and cleared the lookup-savings threshold against both GEPA controls. Its paired accuracy ranges included zero. This experiment freezes the same policy and compares it on 16 model and subject pairs absent from the local CPO correctness snapshots. [Development result](late-miss-substitution.md) · [Frozen design](late-miss-transfer-design-v1.json)

The models are Mixtral 8×7B Instruct and Falcon 180B. The subjects are anatomy, college biology, elementary mathematics, high-school macroeconomics, human aging, professional psychology, sociology, and US foreign policy. Other CPO experiments used these subjects with different models and used these models on other subjects. This design tests transfer across recorded model and subject pairings. It pins the exact PromptEval Parquet objects before retrieving their correctness values. [PromptEval correctness archive](https://huggingface.co/datasets/PromptEval/PromptEval_MMLU_correctness) · [License](../benchmarks/data/LICENSE.prompteval)

The late substitution, original CPO route, official batched and sequential GEPA with a search cap of 52, batched GEPA with cap 47, and retaining the start use the original 32 seeds per panel. The four-cycle schedule has 12 validation cases and eight disjoint qualification cases each cycle, and a separate final holdout. The primary gate requires at least 10% paid lookup savings against both cap-52 GEPA modes and a nonnegative lower endpoint for the joint central 95% paired range. The 4,096 draws resample the original held-out cases within each subject, keeping both models and all episodes together. [Runner](../benchmarks/late_miss_transfer.py)

## Results

The design was on GitHub before any selected correctness object was fetched. It checked 24 workspace snapshots containing 227 distinct named model and subject pairs, with zero overlaps. The replay scored 41,728 decisions per method across 652 distinct held-out cases. [Published design](https://github.com/alvarovillalbaa/cpo/commit/2ba945efe67f0b0300a066e3146b433ae3e98074)

| Method | Holdout passes / 41,728 | Paid lookups |
| --- | ---: | ---: |
| Retain start | 29,562 | 0 |
| Original CPO route | 29,616 | 46,981 |
| Late miss substitution | 29,604 | 47,919 |
| Batched GEPA, cap 47 | 29,584 | 41,675 |
| Batched GEPA, cap 52 | 29,600 | 53,024 |
| Sequential GEPA, cap 52 | 29,625 | 77,567 |

Late substitution lost 12 passes and used 938 more lookups than the original route. Its paired range against that route was −37 to +14. Professional psychology accounted for 16 fewer passes across both models. The other seven subjects together gained four. The screen traded 1,249 tail probes, found 330 alternate misses, and produced 72 finalists from 1,124 alternate probes. [Per-panel outcomes and paid traces](late-miss-transfer-results-v1.json)

The policy saved 9.6% of lookups against cap-52 batched GEPA and 38.2% against sequential GEPA. The joint accuracy range was −89 to +43 passes. The policy missed the savings threshold, and its paired accuracy evidence remained inconclusive. The original route stays in place. The archive measures selection among supplied prompts. Fresh-model performance remains unverified.

The follow-up kept the original screening case until the first finalist failed and then tested a funded retry on untouched candidates. [Finalist retry replay](funded-finalist-retry.md)

## Reproduce

Use the published source revision, pinned GEPA 0.1.4, the bundled snapshot, and a fresh output path. The capture validated all 16 pinned objects before decoding their 2,136,897 bytes with the verified DuckDB 1.4.3 wheel in a temporary overlay. Two socket- and DNS-disabled replays matched byte for byte. The runner rejected a wrong seal, a modified source digest, and an existing output path. Storage Guard measured 11.4 GiB free. The 61.1 MB scratch overlay was removed under the standing LAB exception. [Snapshot](../benchmarks/data/late-miss-transfer-v1.json) · [Verification receipt](late-miss-transfer-verification-v1.json) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.late_miss_transfer \
  --replay benchmarks/data/late-miss-transfer-v1.json \
  --execute da9e227b09e05379f73c537b9fff124f94e6fd13de42a578e0562102490be75a \
  --out NEW_REPORT.json
```
