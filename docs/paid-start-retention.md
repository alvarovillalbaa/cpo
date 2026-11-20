# Test returning to the start with paid evidence

The costed reachability audit found that keeping the starting prompt would have matched GEPA in 109 losing comparisons. That result used final holdout scores. This replay tests whether CPO could identify any of those decisions before scoring the holdout, without buying a fresh guard panel. [Costed reachability](priced-gate-reachability.md) · [Earlier independent guard](prompt-episode-guard.md)

Each episode runs the published CPO search, archive, and qualification unchanged. At the end, the replay compares the final and starting prompts only on cases where both answers were already paid for. It deduplicates validation cache hits, keeps validation and qualification separate, and checks that both ledgers reproduce the original paid lookup counts. Missing counterparts contribute no evidence.

- **Matched pooled** returns to the start if there are at least four matched cases and the start leads by at least two net passes across them.
- **Qualification corroborated** also requires a positive net advantage for the start on the matched qualification subset.

The four-cycle schedule, lookup budget, and decision traces are identical up to final selection. The same recorded replies yield both alternatives. The replay uses the existing 28 Llama, Mistral, Gemma, and Flan panels. The paired comparison against both cap-52 GEPA controls keeps the original requirement of at least 10% savings and a nonnegative lower endpoint. The available pairs were collected adaptively and the rule may favor whichever prompt was evaluated more completely. [Runner](../benchmarks/paid_start_retention.py) · [Previous control comparison](complementary-backup.md)

## Results

CPO finished with a prompt other than the start in 229 of 896 episodes. Neither rule reversed any of those decisions. All three CPO policies scored 17,724 passes with 49,330 lookups on Llama and Mistral and 17,435 passes with 35,496 lookups on Gemma and Flan. Both joint GEPA comparisons remained inconclusive. [Per-panel outcomes and paid evidence counts](paid-start-retention-results-v1.json)

Across the 109 losing comparisons where retaining the start would match GEPA, the start trailed on the paired paid cases in every comparison. There were between 5 and 38 matched cases per comparison. The start trailed in qualification alone in 100 of those comparisons and tied in nine. Across all 229 departed-start episodes its pooled matched score trailed 227 times and tied twice. Lowering the positive margin to one net pass would still have produced zero rollbacks. These counts compare each GEPA control separately and can count an episode twice.

The paid evidence agrees with the decision it helped select. These archives leave no positive head-to-head signal for this rollback rule. A different retention test needs cases reserved from the selection process or needs to change which evidence informs the first promotion. The original selection remains in place.

A follow-up instead moved the existing final-cycle start comparison after fresh search. It gained some held-out passes at greater cost and recovered none of the earlier start-retention losses. [Final-cycle reconciliation replay](final-start-reconciliation.md)

## Reproduce

Use pinned GEPA 0.1.4 and a fresh output path. Two replays in source exports matched byte for byte with sockets and DNS blocked, and reproduced 84 published control traces. The captured ledgers matched original paid costs on every episode. Three focused tests covered missing matches, corroboration, and duplicate observations. The CLI rejected an incorrect seal and preserved an existing output. Storage Guard measured 13.0 GiB free. The 20.1 MB scratch overlay was removed under the standing LAB exception. [Tests](../tests/unit/test_paid_start_retention.py) · [Verification receipt](paid-start-retention-verification-v1.json) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.paid_start_retention \
  --execute 8709b42180c57d7c026ab3bb59d721aae0aad0b217784430e90618a8841d624b \
  --out NEW_REPORT.json
```
