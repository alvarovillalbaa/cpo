# Test two-miss routing on unused model splits

Widening after two incumbent misses beat both cap-52 GEPA controls on an archived MMLU cohort. This follow-up published the candidate, model and subject roster, controls, and acceptance rule before reading the evaluation outcomes. The design commit is `c9f0f1bf3f02beb2daa56e20eafc74a4d5391c41`. [Routing pilot](balanced-finalist-race.md) · [Frozen design](routed-finalist-model-transfer-design-v1.json)

The new panels pair Code Llama 34B Instruct and Merlinite 7B with abstract algebra, business ethics, college mathematics, conceptual physics, human aging, jurisprudence, management, and world religions. Neither model split appeared in the 183 prior archived task and model combinations checked. All eight subjects had archived scores for other models and were absent from the routing pilot. The 16-panel cohort tests transfer to new model outcomes on familiar benchmark subjects. [PromptEval correctness dataset](https://huggingface.co/datasets/PromptEval/PromptEval_MMLU_correctness) · [MIT notice](../benchmarks/data/LICENSE.prompteval) · [Captured outcomes](../benchmarks/data/routed-finalist-model-transfer-v1.json)

All settings receive the same 32 four-cycle episodes per panel, starts and proposal blocks, 12 validation cases per cycle, recency archive, and independent eight-case qualification. The candidate widens to a six-candidate screen only when its incumbent fails the first two validation cases. It uses the deferred first-gain selector in other cycles. The baseline and always-wide CPO arms use the same cap of 52. The two primary controls use official batched and sequential GEPA 0.1.4 at cap 52. Batched cap 44 and sequential cap 31 are frozen secondary controls. [Replay runner](../benchmarks/routed_finalist_model_transfer.py)

The primary gate requires at least 10% lookup savings against both primary controls and a nonnegative lower endpoint of the central 95% paired range. Each of 4,096 draws resamples cases within subject, keeps both models and all episodes together, and takes the smaller CPO pass difference against the two controls. This is a range over the 339 archived holdout cases and their fixed trajectories.

## Results

| Method | Holdout passes / 21,696 | Paid lookups |
| --- | ---: | ---: |
| Retain start | 12,107 | 0 |
| Seeded CPO | 12,165 | 46,040 |
| CPO, widen after two misses | 12,223 | 57,283 |
| CPO, always wide | 12,253 | 80,684 |
| Batched GEPA, cap 44 | 12,164 | 41,467 |
| Batched GEPA, cap 52 | 12,181 | 57,817 |
| Sequential GEPA, cap 31 | 12,188 | 41,108 |
| Sequential GEPA, cap 52 | 12,253 | 83,250 |

The two-miss candidate gained **42 passes and saved 0.9% of lookups** against primary batched GEPA. It saved **31.2% of lookups** against primary sequential GEPA while scoring **30 fewer passes**. The joint paired range was **−90 to +30 passes**. The frozen gate **failed** because the savings against batched GEPA fell below 10%. The candidate led batched GEPA on both model splits and remained behind sequential GEPA after omitting any single subject. [Sealed results](routed-finalist-model-transfer-results-v1.json)

The policy widened 420 times across 2,048 scheduled cycles. Compared with seeded CPO, it gained 58 passes, with a paired range of +21 to +95, and spent 11,243 more lookups. It saved 23,401 lookups against always-wide CPO and lost 30 passes. The two lower-cap GEPA arms both spent less than the routed candidate and scored fewer passes. The seeded CPO default remains in place.

A decision-equivalent validation proof saved a further 402 routed lookups without changing the selected prompts. [Finalist score bounds](finalist-bound-replay.md)

## Capture and replay

The row viewer returned 502s and timeouts. The fallback fetched the same 16 score matrices directly from the dataset revision frozen in the design. It verified each Parquet file against the revision's object metadata and recorded its exact SHA-256 and byte length. The decoder also reproduced a previously captured abstract-algebra viewer matrix byte for byte at the correctness-vector level. The capture reused a temporary, hash-verified DuckDB 1.4.3 wheel and left the frozen experiment and project dependencies unchanged. [Parquet capture helper](../benchmarks/routed_finalist_parquet_capture.py)

Use pinned GEPA 0.1.4 and a fresh output path. The committed snapshot supplies the replay inputs.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.routed_finalist_model_transfer \
  --replay benchmarks/data/routed-finalist-model-transfer-v1.json \
  --execute dca8079ca59b5b5865eda282897ebf409d443899424d5d4a63c877a6bf16f155 \
  --out NEW_REPORT.json
```

Two offline runs from the frozen source commit with sockets and DNS blocked matched byte for byte. Four focused tests passed. The CLI rejected a stale seal and refused to overwrite an existing report. Storage Guard measured at least 15.9 GiB free. The standing LAB exception covered the 1.1 MB dataset capture, the 52.8 MB temporary decoder, and the 11.6 MB replay overlay. The scratch paths were removed. Fresh prompt generation and provider costs remain unverified.
