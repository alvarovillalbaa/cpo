# Compare recorded critical-coverage search at realized cost

The earlier Sol replay compared coverage-first CPO and official GEPA at search caps 24 and 36. The optimizers used different lookup counts within those caps. This sweep measures both GEPA modes and CPO at eleven caps from 8 through 48, using the original starts, candidate rosters, 220 splits per task, scoring, and paired qualification. Retaining the start gives a zero-lookup reference. At each CPO cost, the retrospective comparison chooses the highest-scoring affordable fixed control, breaking ties by lower cost. It also reports the cheapest measured control that could match each CPO score. [Earlier protocol](recorded-coverage-confirmation.md) · [Runner](../benchmarks/recorded_coverage_frontier.py)

## Reuse the incumbent qualification precheck

The second replay accounts for reading incumbent qualification cases until the first miss or a complete passing panel. A passing panel rules out a strict gain for every challenger. The replay can skip that search while preserving the deployed prompt. When the first miss arrives and ordinary search nominates a challenger, qualification reuses the incumbent replies. If search keeps the incumbent, any precheck evidence is still charged. Both GEPA modes and CPO receive the same rule. [Precheck API](qualification-precheck.md)

## Results

Ticket and warehouse retained 660 and 605 holdout passes respectively across the sweep, including when simply retaining the start. Outage accounts for every measured quality difference. The table reports selected outage points with the precheck on all methods. Cells show holdout passes out of 660 and realized lookup counts.

| CPO search cap | CPO passes / lookups | Strongest affordable GEPA | GEPA passes / lookups | Critical passes CPO lost to that control |
| --- | ---: | --- | ---: | ---: |
| 24 | 457 / 3,324 | Sequential, cap 24 | 396 / 3,077 | 0 |
| 32 | 479 / 3,875 | Batched, cap 36 | 406 / 3,684 | 1 |
| 36 | 485 / 4,059 | Sequential, cap 32 | 410 / 4,016 | 0 |
| 48 | 512 / 4,313 | Sequential, cap 32 | 410 / 4,016 | 0 |

At cap 48, CPO gained 102 passes over the strongest affordable GEPA setting for 297 more lookups. The highest-scoring measured GEPA point at any cost was sequential at cap 48, with 437 passes and 5,736 lookups. It did not match CPO's score within the tested range. The same-cost comparison still includes the critical loss at CPO cap 32. Each cap reuses the same 12 original outage cases across 220 holdouts. Choosing caps from these outcomes describes the measured archive and leaves performance on unseen cases and newly generated prompts open.

At cap 48 the precheck preserved CPO's 1,777 pooled passes and reduced lookups from 8,821 to 5,290. It skipped 469 of 660 searches. Ticket and warehouse accounted for 413 skips. Retaining those two starts also reproduces their holdout scores and has zero search and qualification cost in this replay. [All points, score matches and critical losses](recorded-coverage-frontier-results-v1.json)

A follow-up used one shared validation case to prioritize small groups of challengers and brought the cap-48 CPO result below the prior fixed GEPA lookup count. [Challenger screening replay](recorded-coverage-window.md)

## Reproduce

Use the intact GEPA research and Open Evals archives with pinned GEPA 0.1.4.

```sh
PYTHONPATH=/path/to/gepa-research PYTHONHASHSEED=0 python -B -m benchmarks.recorded_coverage_frontier
PYTHONPATH=/path/to/gepa-research PYTHONHASHSEED=0 python -B -m benchmarks.recorded_coverage_frontier \
  --execute 1ffb81113d95f8b02d3a1f91e99958059f14ce611382401a08fe8f6f3ae27920 \
  --out NEW_REPORT.json
```

Two exact-source replays matched byte for byte with sockets and DNS blocked. They reproduced both published caps on all tasks and retained the original cost frontier and matched comparisons after adding the precheck. Thirteen focused tests passed. The CLI rejected an incorrect seal and an existing output path. Storage Guard measured 14.6 GiB free. The 19.0 MB temporary source and wheel overlay was removed under the standing LAB exception. [Verification receipt](recorded-coverage-frontier-verification-v1.json)
