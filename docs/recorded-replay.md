# Recorded model-reply replay

The research archive contains recorded outcomes for candidate prompts in ticket routing, warehouse release, and outage credits. We evaluated the CPO implementation on a fixed, parent-linked proposal graph and compared it with official GEPA 0.1.4 using sequential and two-proposal batched selection. Each task used 20 seeded splits of 12 recorded rows, with four rows in each of training, validation, and replay holdout. The gate required zero matched critical losses per task and either more exact passes at equal or lower search cost or equal passes with at least 10% fewer calls. Costs count evaluator lookups and requested proposal slots, including slots with no recorded proposal.

The first replay missed the gate. Warehouse tied sequential GEPA on passes but used 461 calls versus 508, a 9.3% reduction. We then added an explicit exhaustion signal for finite proposers and tested it on disjoint seeds.

| Task | CPO calls | Sequential GEPA calls | Batched GEPA calls | CPO exact pass gain vs sequential / batched |
| --- | ---: | ---: | ---: | ---: |
| Ticket | 240 | 517 | 586 | 34 / 32 |
| Warehouse | 340 | 563 | 610 | 0 / 0 |
| Outage | 565 | 997 | 1,068 | 8 / 3 |

CPO lost zero matched critical cases in the second replay. On the same splits, the control with rewrite ordering alone also cleared the GEPA gate. The exhaustion signal preserved all 60 selected prompts and reduced calls from 1,399 to 1,145. That matched comparison isolates the effect of stopping proposals from an exhausted parent.

The repeated splits share archived rows and candidates. The source trial’s separate holdout was available for both selected prompts in 27 of 60 splits against sequential GEPA and 28 against batched GEPA. The gate uses replay holdout rows and does not establish fresh proposal quality, live request timing, or provider spend. Raw replies and the paired replay driver remain with the original study archive. The shipped synthetic benchmark is self-contained.
