# Test four-case CPO qualification on new archived subjects

The earlier replay found that four distinct qualification cases improved seeded CPO's score and lookup cost on two archived cohorts. This follow-up published the four-case candidate, official GEPA comparators, resampling procedure, and acceptance rule before reading the outcomes. The design commit is `b5c20e35282223edb2d3bb3a5e954f4a07375e77`. [Earlier replay](qualification-repeat-sensitivity.md) · [Frozen design](four-case-qualification-transfer-design-v1.json)

The new panels cover college chemistry, college medicine, human sexuality, medical genetics, professional law, and virology on Flan-T5 XL and Llama 3 70B Instruct. The subject and model split names were absent from the 16 existing local snapshots. The capture verified the source revision and license before and after retrieving the 12 panels. Each panel contains 100 prompt templates and retains the SHA-256 and byte length of each source page. [PromptEval correctness archive](https://huggingface.co/datasets/PromptEval/PromptEval_MMLU_correctness) · [MIT notice](../benchmarks/data/LICENSE.prompteval) · [Captured scores](../benchmarks/data/four-case-qualification-transfer-v1.json)

All methods receive the same 32 seeded four-cycle episodes per panel, starts, proposal blocks, validation cases, and recency archive. Four-case methods read from the first four of the same eight reserved qualification cases. The primary controls are the official sequential and batched GEPA 0.1.4 modes with eight qualification cases and the same paid search cap of 52. The study also measures batched GEPA on four cases and the previously strong eight-case cap of 44. [Replay runner](../benchmarks/four_case_qualification_transfer.py)

The primary gate requires at least 10% lookup savings against each primary control and a nonnegative lower endpoint for the central 95% paired range. Each of the 4,096 draws resamples the 659 distinct holdout cases within their subjects. The draw keeps both models and all episodes for the sampled case together and records the smaller CPO pass difference against the two controls. The range is conditional on these subjects, prompt pools, and trajectories. There are 42,176 repeated holdout decisions per method.

## Results

| Method | Holdout passes | Paid lookups |
| --- | ---: | ---: |
| Retain start | 22,258 | 0 |
| CPO, four cases, cap 52 | 22,292 | 26,411 |
| CPO, eight cases, cap 52 | 22,334 | 29,572 |
| Batched GEPA, four cases, cap 52 | 22,343 | 37,558 |
| Batched GEPA, eight cases, cap 44 | 22,334 | 28,384 |
| Batched GEPA, eight cases, cap 52 | 22,352 | 38,990 |
| Sequential GEPA, eight cases, cap 52 | 22,361 | 56,504 |

Four-case CPO saved **32.3%** of lookups against primary batched GEPA and **53.3%** against primary sequential GEPA, while scoring 60 and 69 fewer passes, respectively. The simultaneous paired range was **−118 to −35 passes**. The preregistered gate **failed**.

The four-case schedule saved 3,161 lookups and lost 42 passes against eight-case CPO. The paired range was −77 to −8. Professional law accounted for 25 of those lost passes and 55 of the 60 lost against cap-52 batched GEPA. Omitting law left CPO behind eight-case CPO by 17, primary batched GEPA by five, and primary sequential GEPA by 13 passes. The lower-cost batched cap-44 arm scored 42 more passes than four-case CPO for 1,973 more lookups. These new panels reverse the earlier within-CPO quality gain. The eight-case default remains in place. [Sealed panel results](four-case-qualification-transfer-results-v1.json)

A retrospective follow-up found that all 37 promotions missed at the first divergence began with a four-case tie. Extending ties recovered 51 passes over the shorter schedule on these panels and still finished below both primary GEPA controls. [Tie extension and loss attribution](qualification-role-transfer.md)

Two executions with sockets and DNS blocked produced identical reports. Four focused tests passed, and the replay refused both a stale seal and an existing output path. Storage Guard measured 13.6 GiB free. The standing LAB exception covered the bounded capture and temporary pinned wheel overlay. The public pages totalled 8.5 MB and the reduced corpus is 476 KB. The 10.3 MB scratch tree was removed. This is prospective evidence on new archived scores. Fresh prompt generation and live provider costs remain unverified.

## Reproduce

Use pinned GEPA 0.1.4 and a fresh output path. The committed corpus is sufficient for offline replay.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.four_case_qualification_transfer \
  --replay benchmarks/data/four-case-qualification-transfer-v1.json \
  --execute 89d6273b9142f51230bdafea0037c664522e9b343e0c09091d4bff6f2c66f1a2 \
  --out NEW_REPORT.json
```
