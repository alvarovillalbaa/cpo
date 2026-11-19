# Training probes that stop at the first error

CPO normally takes two training observations before asking the proposer for its next repair in this benchmark. This study tests two alternatives. The first stops at the first exact error, up to the usual two-example limit. The second does the same after moving critical training cases ahead of ordinary cases in the seeded order. Both use the same opening pair, evaluator, proposer, validation rules, and split-level budget. Holdout examples stay separate.

## Deterministic fixture

The follow-up ran 12 new fixture seeds across three typed tasks with two scripted proposers. At a cap of 56 evaluation lookups per task and arm, the proposer that requires an observed error produced these results. The call totals include evaluations and reflection calls, with the shared opening charged once per arm.

| Search | Held-out exact passes | Search calls | Cleared the fixture gate vs GEPA |
| --- | ---: | ---: | --- |
| Fixed two probes | 648 | 1,155 | No |
| First error | 648 | 1,148 | No |
| Critical-first error | 648 | 1,096 | Yes |
| Field-aware sequential GEPA | 646 | 1,218 | Reference |

Critical-first error preserved all matched critical passes and saved 122 calls against GEPA, just over the 10% threshold. At a cap of 40, it recovered 17 passes over fixed probing with the error-dependent proposer and increased search calls from 1,032 to 1,079. The other proposer and the lower caps are included in the report. [Fixture result](feedback-probe-policy-fixture-v1.json)

## Recorded proposal graph

The archived model replies supply a fixed proposal graph. This replay can measure selection and cost when the feedback schedule changes. The archived proposer traverses the same recorded children regardless of which training observations it receives. Each task uses 40 newly seeded splits of the same archived rows.

At an evaluation cap of 144, critical-first error matched fixed CPO on all three tasks, preserved every matched critical pass, and lowered charged outage search calls from 1,033 to 1,008. It tied field-aware sequential GEPA on outage passes and trailed the batched control by three. At a cap of 24, the two CPO versions still tied on passes and critical cases, while critical-first error raised outage calls from 904 to 932. Ticket and warehouse call counts were identical under both CPO schedules at each cap. The lower-cap comparison uses matched CPO schedules. [Recorded replay result](feedback-probe-policy-recorded-v1.json)

The experiment keeps fixed probing as the default. The fixture shows a benefit when the scripted proposer needs a witnessed error. Fresh model-backed performance with the changed feedback remains unmeasured.

## Reproduce the fixture

In a disposable checkout at the commit containing the report, install the pinned benchmark dependencies and apply the experimental patch.

```sh
python -m pip install --require-hashes -r requirements-benchmark.txt
git apply --unidiff-zero benchmarks/patches/feedback-probe-policy.patch
python -m benchmarks.feedback_probe_policy
python -m benchmarks.feedback_probe_policy --execute PLAN_SHA256 --out result.json
cmp result.json docs/feedback-probe-policy-fixture-v1.json
```

Use the seal printed by the third command. [Benchmark runner](../benchmarks/feedback_probe_policy.py) · [Prototype patch](../benchmarks/patches/feedback-probe-policy.patch)
