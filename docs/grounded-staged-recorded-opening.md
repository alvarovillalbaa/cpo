# Compare staged and opening-only CPO on recorded model replies

A retrospective GPT‑6.2 Sol replay tested whether the [staged fixture gain](grounded-staged-opening-ablation.md) carried over to previously observed model replies. It ran 240 paths across ticket routing, warehouse release and outage credits. Every arm received the same opening pair, search budget, and exact admission rule. Each path reserved two cases for scoring after the search and admission decisions. The 480 scoring uses reuse 36 distinct archived cases. [Sealed comparison and verification](grounded-staged-recorded-opening-results-v1.json)

| Policy | Recorded scoring passes out of 480 | Search and admission lookups | Estimated cost at recorded rates |
| --- | ---: | ---: | ---: |
| Opening-only CPO | 382 | 2,310 | $21.673896 |
| Staged CPO | 382 | 2,824 | $27.219960 |
| Sequential GEPA | 382 | 4,338 | $42.686184 |
| Batched GEPA | 381 | 5,388 | $47.037720 |

Opening-only and staged CPO chose the same prompts in all 240 paths. Staged CPO spent 514 extra search lookups and 25.6% more at the recorded rates. The final validation certificate rejected 69 outage drafts. Opening-only preserved all matched critical passes against both GEPA controls on the replay scoring split. Its estimated cost was 49.2% below sequential GEPA and 53.9% below batched GEPA.

The original study's separate holdout contained matching results for the two CPO policies on all paths. Missing GEPA replies on that holdout left the direction of the quality difference unresolved. This replay uses a fixed proposal graph, so later repair could only try previously recorded edits. The portable fixture isolates the benefit when useful repairs are available. Fresh model proposals still need to be compared against both opening-only and the GEPA controls. The original provider archives are required to reproduce the recorded comparison. The portable fixture remains runnable from this repository.

The prospective protocol now includes both CPO policies as direct controls and binds them to the same independent confirmation panel. [Prospective comparison](grounded-staged-policy-comparison.md)

The receipt audit found that opening-only stayed at least 10% cheaper than both GEPA controls on each task under every matched historical charge assignment. [Recorded cost bounds](grounded-opening-price-bounds.md)
