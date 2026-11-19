# Precomputed openings and feedback budgets

`cpo.search` and `cpo.run_cycle` accept an optional `opening_pair=ProposalPair(rewrite=..., repair=...)`. The supplied pair occupies the first proposal round. Search evaluates it on validation, then uses the configured training probes for subsequent reflection. The pair’s generation takes place outside the optimizer, so cost comparisons charge the shared opening to every arm.

The fixture tests the opening against the callback path at one or two training observations per later reflection. It uses six new seeds, 18 task panels, and 324 exact holdout judgments per arm for each setting. Both optimizers start with the same pre-generated rewrite and repair, may use the same demonstration bundle, and use field credit in search. GEPA 0.1.4 runs rewrite-first sequential search at the same feedback cap. All comparisons include the shared opening in both arms’ attributed cost.

The label-template proposer uses the labeled training examples. The observed-error proposer additionally requires a mismatching field in an evaluated training example before it will repair that field. It counts each observed example once and rejects feedback from outside training. This checks the behavior of smaller feedback batches when the proposer depends on the observations.

## Primary cap of 56 evaluations per task and arm

| Proposer | CPO opening and later feedback | CPO passes / calls | GEPA passes / calls | Matched critical losses | Gate |
| --- | --- | ---: | ---: | ---: | --- |
| Label templates | Callback, two examples | 324 / 591 | 322 / 637 | 0 | Missed |
| Label templates | Precomputed, two examples | 324 / 555 | 322 / 637 | 0 | Passed |
| Observed errors | Callback, two examples | 324 / 629 | 314 / 641 | 0 | Passed |
| Observed errors | Precomputed, two examples | 324 / 567 | 314 / 641 | 0 | Passed |
| Observed errors | Precomputed, one example | 324 / 574 | 320 / 584 | 0 | Missed |

The gate requires at least 14 exact passes in every 18-case panel, preservation of each panel’s total and matched critical passes, and either eight additional exact passes without added calls or a 10% call saving. With two observed examples, the precomputed opening saved 62 calls over the CPO callback path and 74 calls, or 11.5%, versus GEPA. With the label-template proposer it saved 82 calls, or 12.9%, over GEPA.

At the tighter cap of 40, the precomputed opening and two-example error feedback passed 320 cases to GEPA’s 287 and required 36 more calls. One-example error feedback with the precomputed opening lost seven matched critical cases. The low-budget outcomes and the full factorial results are retained in the receipt. These results apply to the deterministic fixture. Model-backed quality and independent confirmation remain open. [Versioned results](feedback-budget-results-v1.json)

## Reproduce

```sh
python -m pip install --require-hashes -r requirements-benchmark.txt
python -m benchmarks.feedback_budget > feedback-budget.json
cmp feedback-budget.json docs/feedback-budget-results-v1.json
```

The receipt includes the source and corpus digests, settings, matched outcomes, and paired judgment hashes. Use the source revision that introduced the receipt for byte-for-byte reproduction. [Runner](../benchmarks/feedback_budget.py) · [Feedback contract tests](../tests/test_feedback_budget.py)

A separate ablation measures when stopping after the first observed error changes the outcome or cost. [Training probe schedules](feedback-probe-policy.md)
