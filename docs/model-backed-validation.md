# Model-backed validation

The typed development study compares the optimizer from CPO 0.2.0 with three GEPA 0.1.4 configurations. The GEPA controls use repair-first sequential, repair-first batched, and rewrite-first sequential selection. All four optimizers share the same generated opening rewrite and repair for each task. They use the same model, typed scorer, train and validation cohorts, and search limits. The starting prompt provides a fifth arm in qualification.

The targets are ticket routing, warehouse release, and outage credits. Selection completes before the development holdout is dispatched. The 54 holdout cases are evaluated twice for every arm. Arms with identical request bytes share a sample within a case and repeat. This prevents stochastic replies to the same prompt from counting as a prompt improvement.

CPO must score at least 27 of 36 replies in each task and preserve the starting prompt’s matched critical passes and task totals. Against each GEPA control, it must preserve task totals and matched critical passes. It must also gain at least eight replies or use at least 10% less search cost without losing any paired case total. Costs use the same sealed token rates for all arms. Case-level statistics group both repeats together.

Independent confirmation uses 24 separate cases and can only bind after development qualifies. Its exact request schedule is sealed from the selected prompt bytes and the audited development archive. The research archive retains the probe credentials separately from the request journals and records the exact responses, paired outcomes, and planned checkpoints. The GitHub repository contains the optimizer and the self-contained synthetic benchmark.

The live comparison tests GEPA selection under those three reflection configurations. OPRO and MIPROv2 informed the treatment of candidate history and the separation of proposal and validation. They have yet to be run as separate controls in this protocol. [GEPA](https://arxiv.org/abs/2507.19457) · [OPRO](https://arxiv.org/abs/2309.03409) · [MIPROv2](https://arxiv.org/abs/2406.11695)
