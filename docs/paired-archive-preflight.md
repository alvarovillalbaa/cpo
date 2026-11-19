# Stop archive qualification once paired bounds settle the decision

The recency archive tries one previously seen prompt before fresh search. The existing check reads the complete incumbent panel and then certifies a strict challenger gain. This replay uses the existing paired qualifier to stop once the observed replies prove or rule out that gain. The challenger replies still debit the same cycle's fresh-search allowance. [Archive policy](prompteval-archive-cycles.md) · [Paired qualification](paired-qualification.md)

The primary gate at cap 52 requires seeded CPO to preserve every search trace and promotion decision and use fewer aggregate paid lookups. The comparison also runs caps 28 and 44 and applies the same qualifier to both official GEPA modes. Changing the actual archive debit can change later search and holdout outcomes even when the archive gate itself agrees. The replay compares each archive decision with the full recorded case panel. The full comparison is an offline assertion and does not supply evidence to the qualifying method. [Runner](../benchmarks/paired_archive_preflight.py)

The same 40 archived model-task panels, starts, proposals, qualification cases, and final holdout apply to both orders. Search costs use distinct paid lookups. Qualification includes both prompts and reuse within the current cohort. The primary result is an exact paired replay on these archives. It does not estimate future model performance.

## Results

| Cap | Method | Incumbent-first passes / lookups | Paired passes / lookups | Episodes with a different final prompt / 1,280 |
| --- | --- | ---: | ---: | ---: |
| 28 | Seeded CPO | 29,434 / 82,759 | 29,418 / 81,123 | 11 |
| 44 | Seeded CPO | 29,994 / 122,511 | 29,994 / 123,164 | 0 |
| 52 | Seeded CPO | 29,994 / 122,511 | 29,994 / 123,164 | 0 |
| 52 | Sequential GEPA | 29,984 / 213,057 | 29,987 / 212,644 | 7 |
| 52 | Batched GEPA | 29,742 / 152,422 | 29,718 / 151,856 | 6 |

At cap 52, seeded CPO preserved all 5,120 cycle decisions and search traces. It used 653 more lookups. Archive checks accounted for 518 additional reads, and the net increase was positive in all four archived cohorts. The paired order therefore failed the primary cost gate. At cap 28 it saved 1,636 lookups and lost 16 holdout passes as changing archive debits changed later search. The incumbent-first archive check remains the reference for this protocol.

Applying the same paired order to GEPA also changed fallback search. At cap 52, sequential GEPA gained three passes and saved 413 lookups, while batched GEPA lost 24 passes and saved 566 lookups. CPO cleared both matched GEPA gates on 17 of 40 panels under either order. [Sealed scores, costs, and traces](paired-archive-preflight-results-v1.json)

Each replay compared 18,234 archive checks with their full-panel decisions and reproduced all 360 published control traces. The unit test exhaustively checked 256 binary archive pairs. Both offline runs per phase produced byte-identical results. Fresh-model quality and provider costs remain unverified.

## Reproduce

Use GEPA 0.1.4. Preview the phase seal, then add `--execute PLAN_SHA256 --out NEW_REPORT.json`. Phases are `independent`, `mmlu`, `bbh-lmentry`, and `bbh-lmentry-stress`.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.paired_archive_preflight --phase independent
```
