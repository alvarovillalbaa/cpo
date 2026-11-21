# Return unread qualification cases to later cycles

An exact paired certificate can settle promotion before it reads every assigned case. This replay tests the effect of returning wholly unread cases to the qualification bank. A case leaves the bank as soon as either prompt receives a grade. Unread base cases join the queue in their original order. Unread cases from an allocated extension stay in their existing positions. A later base tie can use up to four banked cases. The retire-assigned control banks only the cases from cycles that had no challenger. [Runner](../benchmarks/prompteval_qualification_case_reuse.py)

The comparison uses 20 public PromptEval model and subject panels and 640 four-cycle episodes per budget. CPO and both official GEPA 0.1.4 controls use the same supplied proposals, case-level cache rules, shared validation cases, qualification policy, and per-cycle search ceiling. Native GEPA receives stable, disjoint training and validation case IDs. The older PromptEval adapter uses independent positional list loaders, so the new benchmark scopes its correction to this replay. The replay checks every exact certificate against a full recorded evaluation on that cycle's allocated cases. That audit has no effect on the queue, decisions, or paid count.

An initial 76-read check left batched GEPA at incumbent validation throughout. The adapter needs to fund 24 incumbent reads plus up to 56 reads for its first width-two round. The sealed run uses 88 and 136 reads and verifies that batched proposals receive evaluations on every cohort. Paid lookups count distinct search observations within an episode and the grades actually needed for qualification. Proposal generation is supplied by the archive.

## Recorded results

Each cell gives pooled held-out passes and paid lookups across the same 20 panels.

| Search ceiling | Optimizer | Retire assigned cases | Recycle unread cases |
| ---: | --- | ---: | ---: |
| 88 | CPO | 26,042 / 172,814 | 26,051 / 173,074 |
| 88 | Sequential GEPA | 26,023 / 124,361 | 26,030 / 124,397 |
| 88 | Batched GEPA | 25,980 / 67,782 | 25,982 / 67,793 |
| 136 | CPO | 26,043 / 296,981 | 26,033 / 297,357 |
| 136 | Sequential GEPA | 26,050 / 165,870 | 26,057 / 165,893 |
| 136 | Batched GEPA | 26,074 / 153,136 | 26,074 / 153,132 |

Recycling returned 296 previously assigned cases to CPO's bank at cap 88 and 377 at cap 136. It added 260 and 376 paid lookups respectively. The CPO score gained nine passes at cap 88 and lost ten at cap 136. At the wider ceiling, each GEPA mode achieved more pooled passes at lower paid cost than every tested CPO setting. This archive gives no basis for making recycling the default. It also shows that matching hard ceilings leaves different amounts of work available to each search policy. [Per-panel results and journal digests](prompteval-qualification-case-reuse-results-v1.json)

A follow-up uses the retire-assigned policy and the same case schedule to compare cheaper CPO challenger screens. [Rotating validation witnesses](prompteval-first-proof-budget.md)

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. The runner uses the tracked correctness matrices and a fresh output path. Each episode reads the final holdout only after all four optimization cycles. The same archive cases recur across seeds. Live generation cost and generalization to fresh model outputs remain unmeasured. [Benchmark wheel](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.prompteval_qualification_case_reuse
PYTHONHASHSEED=0 python -B -m benchmarks.prompteval_qualification_case_reuse \
  --execute cf3c2ac4a8b1e005e3df10e7ad53cab75830757fb28f961b513714e84b128759 \
  --out NEW_REPORT.json
```

The recorded receipt SHA-256 is `8b4f131ab07cf6df635240b8158437e326fd9282c16a41861b84a0c023459308`. Verification used disposable source and wheel overlays bounded at 0.2 GiB. Storage Guard measured 9.4 GiB free. The standing LAB exception covered the overlays, with sockets and DNS blocked. [Qualification contract tests](../tests/unit/test_prompteval_qualification_case_reuse.py)
