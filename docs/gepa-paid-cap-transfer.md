# Give GEPA the same paid search ceiling after cache reuse

The matched-cost replay credited CPO and GEPA for identical evidence reused within an episode. Its original logical caps still controlled search. This follow-up lets both official GEPA 0.1.4 controls use cache savings to enter additional rounds. It keeps the frozen four-cycle schedule, proposal roster, independent qualification, and archive nomination rule on all 32 transfer panels. [Matched-cost replay](bounded-transfer-matched-cost.md)

The original search ceiling is 52 paid lookups per cycle, with the archive challenger charge deducted before fresh search. The GEPA adapter still reserves enough for an entire sequential or batched round. It tests that reserve against the number of fresh search lookups already paid in the current cycle. Its evaluator guards the paid ceiling before every cache miss. The seeded search and qualification cases are disjoint. Qualification still stops at the first decisive reply.

The deferred first-gain CPO reference reserves at most 35 logical search lookups for the entire 12-challenger pool. Even with the largest archive challenger charge, it has 44 search slots. Its proposal order, decisions, and matched-cache lookup counts are therefore the published reference for this intervention. The runner also reproduces every original logical-cap GEPA trace before comparing final prompts and scores.

This comparison permits deeper GEPA search over the same supplied prompt roster. The recorded lookup cost and holdout scores describe deterministic replay. Reused evidence remains local to one optimizer and episode. [Benchmark runner](../benchmarks/gepa_paid_cap_transfer.py)

## Results

| Method | Holdout passes | Paid lookups |
| --- | ---: | ---: |
| Deferred first-gain CPO | 21,023 | 101,034 |
| Sequential GEPA, original logical ceiling | 20,865 | 140,003 |
| Sequential GEPA, paid ceiling | 20,992 | 170,448 |
| Batched GEPA, original logical ceiling | 20,427 | 103,045 |
| Batched GEPA, paid ceiling | 20,746 | 123,137 |

Reinvesting cache savings added 127 passes and 30,445 lookups for sequential GEPA and 319 passes and 20,092 lookups for batched GEPA. Sequential and batched GEPA exceeded the old logical ceiling in 933 and 45 cycles, respectively. The highest observed paid search counts, including the archive challenger charge, were 50 for sequential and 47 for batched, both within the cap of 52.

Against these paid-cap controls, deferred first-gain finished **31 passes ahead of sequential GEPA with 40.7% fewer lookups** and **277 passes ahead of batched GEPA with 17.95% fewer lookups**. It met both accuracy-and-cost gates on 15 of 32 panels. The GEPA arms changed their search depth and realized costs while CPO used its existing fixed pool policy.

The aggregate accuracy lead over batched GEPA survived omission of any one subject and both of its model panels, with a minimum lead of 132 passes. Omitting LMentry's any-words-from-category task reversed the 31-pass aggregate accuracy lead over sequential GEPA. The lookup advantage against each control survived all single-task omissions. Both offline runs of every phase produced byte-identical reports. [Per-panel results and seals](gepa-paid-cap-transfer-results-v1.json)

A follow-up ranked archived CPO prompts using earlier paid qualification. Requiring a prior paired win saved 5,729 lookups and cleared fewer panel-level GEPA gates than the original recency rule. [Archive complementarity replay](archive-complementarity-transfer.md)

## Reproduce

Use pinned GEPA 0.1.4. Preview each phase to get its seal, then add `--execute PLAN_SHA256 --out NEW_REPORT.json`.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.gepa_paid_cap_transfer --phase mmlu
```

The other phases are `bbh-lmentry` and `bbh-lmentry-stress`.
