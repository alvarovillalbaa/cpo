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

## Field-aware selection

A matched ablation used 60 new seeded splits of the same archive. With exact scoring fixed for qualification, field credit saved 20 search calls on warehouse release and 12 on outage credits. Ticket routing used the same number of calls. The two variants tied on exact replay holdout passes across all three tasks, with zero matched critical losses. Field credit changed three warehouse prompt selections. Both variants cleared the replay gate against the two GEPA controls.

Field credit remains opt-in. In a deterministic test, the optimizer kept a partial repair through a zero-exact plateau and reached a complete rule on the next round. A separate test verified that partial credit could not override a previously passing critical example.

## Precomputed opening against field-aware GEPA

A later replay gave CPO and both official GEPA configurations the same recorded opening rewrite and local repair. Both GEPA controls used field-aware scoring and began with the recorded rewrite. Every arm was charged for one shared opening, each evaluation lookup, and each requested proposal slot outside the opening. This accounting describes the replay, including the supplied proposal pair.

Across two sets of 40 seeds per task, precomputed CPO selected the same prompts as callback CPO on all 240 splits and saved two lookups on every split. It cleared the gate against sequential and batched field-aware GEPA on all three tasks in each seed set, with zero matched critical losses. The table shows the second seed set.

| Task | Precomputed CPO calls | Sequential GEPA calls | Batched GEPA calls | Added holdout passes vs sequential / batched |
| --- | ---: | ---: | ---: | ---: |
| Ticket routing | 360 | 440 | 628 | 0 / 0 |
| Warehouse release | 567 | 860 | 1,070 | 0 / 0 |
| Outage credits | 1,013 | 1,803 | 1,964 | 0 / 2 |

Retaining two parents with equal validation scores was also tested on 120 replay splits with new seeds. It changed 19 selections, spent 560 more calls than the default CPO, and gained zero holdout passes. The optimizer keeps its existing tie behavior.

The seed sets reuse the recorded rows and proposal graph. The result isolates search efficiency. Fresh proposal quality, provider timing, and provider spend remain unmeasured. [Precomputed opening API](feedback-budget.md)

An audit against the retained provider token receipts found a pooled historical cost advantage. Ticket routing missed the per-task 10% savings threshold against sequential GEPA when priced by those receipts. [Historical token-cost results](recorded-opening-token-cost.md)
