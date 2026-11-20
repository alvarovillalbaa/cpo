# Prove the same validation winner with fewer replies

The balanced finalist race improved holdout accuracy at a higher validation cost. This replay tests whether the same two finalists can produce the same winner with fewer reads. It measures the six-candidate race when it runs in every fresh search and when it runs only after two incumbent misses. Both retain the original proposal order, shortlist, cap, archive, and eight-case qualification. [Original finalist race](balanced-finalist-race.md) · [Model-split transfer](routed-finalist-model-transfer.md)

## Exact decision from partial scores

The incumbent and the two shortlisted candidates each have a lower score bound equal to observed passes and an upper bound that also counts unread cases. A prompt wins as soon as its lower bound outranks every eligible rival's upper bound under the original tie order. A challenger must also show it preserves all critical validation cases the incumbent passed. The next-read heuristic looks for a pass to raise a contender's lower bound or a failure to lower a rival's upper bound. It estimates those outcomes only from paid replies. A favorable estimate never settles a comparison. [Bound selector](../benchmarks/finalist_score_bounds.py)

The eager version initially measures the whole incumbent. The deferred version begins screening as soon as it has identified the same first incumbent miss and pass used by the original screen. It reads any remaining incumbent critical cases before deciding. Additional incumbent replies are purchased only when they can still matter to the exact comparison. The original full-race reserve is required in both versions, and the benchmark stops before any read that would exceed it. [Exact reference](../benchmarks/balanced_finalist_race.py) · [Exhaustive comparison test](../tests/unit/test_finalist_score_bounds.py)

## Results

All three columns preserve the holdout score shown. The cost columns include distinct search and qualification lookups.

| Cohort and policy | Holdout passes | Original race | Eager bounds | Deferred bounds |
| --- | ---: | ---: | ---: | ---: |
| BBH and LMentry, always wide | 3,467 | 66,768 | 65,606 | 65,504 |
| BBH and LMentry, two-miss routing | 3,429 | 55,332 | 54,345 | 54,280 |
| MMLU pilot, always wide | 22,464 | 56,591 | 56,533 | 56,506 |
| MMLU pilot, two-miss routing | 22,390 | 37,902 | 37,814 | 38,019 |
| MMLU model transfer, always wide | 12,253 | 80,684 | 79,956 | 79,716 |
| MMLU model transfer, two-miss routing | 12,223 | 57,283 | 56,881 | 56,902 |

Deferred bounds saved **2,317 lookups** across the three always-wide comparisons. Eager bounds saved **1,477 lookups** across the routed comparisons. The deferred route added 117 lookups on the MMLU pilot. Query ordering can spend more in individual episodes while preserving every decision. [Per-panel lookup ledgers](finalist-bound-replay-results-v1.json)

On the model-transfer cohort the eager routed variant used 56,881 lookups, **1.6% fewer** than batched GEPA's 57,817. Its holdout score remained 30 passes behind sequential GEPA. The deferred always-wide variant tied sequential GEPA's 12,253 passes and used 3,534 fewer lookups, while batched GEPA remained substantially cheaper. These retrospective cost reductions do not clear the earlier transfer gate. The released default is unchanged.

## Reproduce

Use pinned GEPA 0.1.4. Preview each phase for its seal. The other phases are `bbh-lmentry` and `mmlu`.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.finalist_bound_replay --phase model-transfer
PYTHONHASHSEED=0 python -B -m benchmarks.finalist_bound_replay \
  --phase model-transfer --execute f6af6b7ca2c24dba5fff09f91c7a629c90d906ba7189197ef4732ab004213bf5 \
  --out NEW_REPORT.json
```

Two offline replays per cohort matched byte for byte. Both variants preserved the original nominee, promotion, qualification trace, and final holdout score in all 20,480 paired cycle checks. All 80 original CPO panel traces reproduced. The unit test checked both bound policies on 4,096 binary matrices, including critical protection and exact paid counts. The CLI rejected a stale seal. Storage Guard measured 15.8 GiB free, and the 11.9 MB scratch overlay was removed under the standing LAB exception. The data are deterministic archived outcomes. Fresh proposal quality and provider costs remain unverified. [Replay runner](../benchmarks/finalist_bound_replay.py)

The follow-up tests whether the shortlist can be settled before completing the probes and measures when paying for a second finalist improves the outcome. [Early screening and backup finalists](finalist-screen-budget.md)
