# Test empty-slot skipping on a second proposal archive

This transfer uses recorded GPT-6.2 Sol replies on ticket routing, warehouse release, and outage credits. It compares CPO’s prior perfect-minibatch rule and the empty-slot extension with native sequential GEPA 0.1.4. Both GEPA skip controls use the same finite proposal information as CPO. One keeps its original reserve and one reserves only work that can proceed. Each of the five budget points uses the same 240 matched paths. The three original Sol budgets reproduced their published CPO and GEPA path hashes. The two additional budgets use the ARC study’s quote points and the Sol study’s 56-read cap. [ARC protocol](recorded-arc-native-empty-slots.md) · [Sol transfer results](recorded-sol-empty-slots-results-v2.json)

| Evaluation quotes | Prior CPO search reads | CPO search reads with empty-slot skipping | CPO cost at recorded rates | Cheapest GEPA skip control at recorded rates |
| ---: | ---: | ---: | ---: | ---: |
| 16 | 2,031 | 2,031 | $24.26 | $29.00 |
| 20 | 2,150 | 2,150 | $25.07 | $30.94 |
| 24 | 2,353 | 2,353 | $26.53 | $31.57 |
| 32 | 2,791 | 2,764 | $32.67 | $38.11 |
| 60 | 2,913 | 2,872 | $34.42 | $46.50 |

All arms matched on the 382 passes across 480 held-out uses drawn from the original development cases. At 60 quotes, CPO cost 26.0% less than both matched GEPA controls. Skipping empty slots saved CPO 41 reads and $0.321336 relative to its prior policy at that budget. CPO kept its original nominee and admission decision on every path. The shortcut had no effect at the three smaller budgets.

The original study’s separate 18-case provider holdout yields a more limited result. At 60 quotes, CPO and GEPA selected identical prompts on 230 of 240 paths. The ten disagreements all came from outage. Two prompt versions lacked any of their 18 separate holdout replies. The 36 missing prompt-case outcomes account for 180 paired scoring uses once repeated selections are counted. Sharing each missing outcome across the paths that use it gives a CPO minus GEPA bound of **−54 to +54** on those weighted comparisons. The range also permits critical losses. The separate provider holdout leaves neither policy’s quality advantage established at the wider budget. [Prior archive holdout audit](recorded-independent-holdout.md)

The private Sol study runner `audit_sol_empty_slots.py` reproduces the aggregate receipt using the original research archive, the pinned CPO revision, and GEPA 0.1.4. Its seal and source hashes are in the result. Two DNS- and socket-blocked replays matched byte for byte. The exact provider replies and case-level gap list stay in the research archive. The replay sent zero provider requests.

The follow-up reconstructed the two missing finalists’ 36 request slots and the full 54-slot matched panel using the original SDK and grader. [Offline panel and scorer](recorded-sol-provider-holdout.md)
