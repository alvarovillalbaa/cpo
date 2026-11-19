# Model-backed validation

The typed development study compares the optimizer from CPO 0.2.0 with three GEPA 0.1.4 configurations. The GEPA controls use repair-first sequential, repair-first batched, and rewrite-first sequential selection. All four optimizers share the same generated opening rewrite and repair for each task. They use the same model, typed scorer, train and validation cohorts, and search limits. The starting prompt provides a fifth arm in qualification.

The targets are ticket routing, warehouse release, and outage credits. Selection completes before the development holdout is dispatched. The 54 holdout cases are evaluated twice for every arm. Arms with identical request bytes share a sample within a case and repeat. This prevents stochastic replies to the same prompt from counting as a prompt improvement.

CPO must score at least 27 of 36 replies in each task and preserve the starting prompt’s matched critical passes and task totals. Against each GEPA control, it must preserve task totals and matched critical passes. It must also gain at least eight replies or use at least 10% less search cost without losing any paired case total. Costs use the same sealed token rates for all arms. Case-level statistics group both repeats together.

Independent confirmation uses 24 separate cases and can only bind after development qualifies. Its exact request schedule is sealed from the selected prompt bytes and the audited development archive. The research archive records the exact responses, paired outcomes, and planned checkpoints. The GitHub repository contains the optimizer and the self-contained synthetic benchmark.

The live comparison tests GEPA selection under those three reflection configurations. OPRO and MIPROv2 informed the treatment of candidate history and the separation of proposal and validation. They have yet to be run as separate controls in this protocol. [GEPA](https://arxiv.org/abs/2507.19457) · [OPRO](https://arxiv.org/abs/2309.03409) · [MIPROv2](https://arxiv.org/abs/2406.11695)

## First live result

The GPT‑6 Luna development trial finished and replayed offline. CPO 0.2.0 and the starting prompt passed 0 of 108 holdout replies. Each GEPA control passed 1 of 108, on outage credits. Development used 491 search requests and 216 holdout requests. The failed development gate prevented independent confirmation.

CPO selected the starting prompt for every task. The search journal showed that all 12 ticket reflections omitted the canonical queue labels and that 115 validation replies across warehouse and outage had some correct fields with no exact pass. CPO 0.3.0 addresses the second problem with optional field credit. Its matched recorded-reply comparison tied the exact scoreboard and used 32 fewer search calls, with no matched critical losses. Its fresh model-backed performance remains open. [Field-aware replay](recorded-replay.md#field-aware-selection)

## Grounded follow-up

The follow-up gives every optimizer all 16 labeled training examples in each reflection and explicitly allows canonical output values. It keeps the same policies while generating fresh case facts for search, development holdout, and independent confirmation. The CPO candidate enables field credit and provides bounded excerpts and aggregate validation counts from candidate history. Final scoring remains exact. The scripted verification exercised paired scoring and checkpoint replay. [Corpus generator](../benchmarks/typed_policy.py) · [Corpus tests](../tests/test_typed_policy.py)
