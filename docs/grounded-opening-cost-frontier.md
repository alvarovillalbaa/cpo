# Compare opening-only CPO with GEPA at matched cost

**Historical baseline.** This replay used GEPA 0.1.4 list loaders, whose overlapping positions can reuse training replies during validation. The split-safe replay and the separate fixed-opening control are the current comparison evidence. [Cache correction and rerun](grounded-gepa-cache-controls.md)

This replay evaluates both native GEPA modes at every integer search cap from 4 through 56. All 240 paths keep the original Sol prompts, proposal graph, case splits, admission certificate, and historical token charges. Only the GEPA evaluation cap changes. The comparison allows retaining the starting prompt at zero cost. It picks the highest-scoring affordable control, breaking ties by lower historical cost. A second comparison lets the control choose a different mode and cap for each task from the same pooled budget. These choices use archived scores in hindsight. [Original opening-only replay](grounded-staged-recorded-opening.md) · [Full results and verification](grounded-opening-cost-frontier-results-v1.json)

| Policy or comparison | Passes out of 480 | Estimated cost |
| --- | ---: | ---: |
| Opening-only CPO | 382 | $21.673896 |
| Best affordable task-specific control | 305 | $16.518480 |
| Cheapest native GEPA point matching CPO's score and critical cases | 382 | $25.712304 |
| Same GEPA point with every training charge waived | 382 | $20.165376 |

No single GEPA mode and cap within the pooled CPO cost improved on retaining the starting prompts. The best task-specific allocation used sequential GEPA at cap 12 for ticket and warehouse and retained the outage starting prompt. It lost 46 critical passes that CPO preserved. Sequential GEPA at cap 12 was the cheapest native point matching CPO across all three tasks. It matched the score and critical outcomes in both seed sets. Opening-only used 15.7% less at the recorded prices.

The counterfactual makes all 960 measured GEPA training lookups free and retains their replies and the original decision path. It reverses the cost comparison by $1.508520. This prices the training evidence at zero and leaves open whether actual execution could obtain equivalent evidence without paying for those reads. [Training cost breakdown](grounded-opening-cost-frontier-results-v1.json)

Both complete offline sweeps produced identical reports. The cap-56 reference reproduced the original traces, and the opening-only hashes remained equal through the sweep. The scoring paths reuse the same 36 archived cases. These results establish a matched-cost comparison within this GEPA setup and archived graph. Fresh model quality and billing remain open.
