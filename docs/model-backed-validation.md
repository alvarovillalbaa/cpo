# Model-backed validation

The typed development study compares the optimizer from CPO 0.2.0 with three GEPA 0.1.4 configurations. The GEPA controls use repair-first sequential, repair-first batched, and rewrite-first sequential selection. All four optimizers share the same generated opening rewrite and repair for each task. They use the same model, typed scorer, train and validation cohorts, and search limits. The starting prompt provides a fifth arm in qualification.

The targets are ticket routing, warehouse release, and outage credits. Selection completes before the development holdout is dispatched. The 54 holdout cases are evaluated twice for every arm. Arms with identical request bytes share a sample within a case and repeat. This prevents stochastic replies to the same prompt from counting as a prompt improvement.

CPO must score at least 27 of 36 replies in each task and preserve the starting prompt’s matched critical passes and task totals. Against each GEPA control, it must preserve task totals and matched critical passes. It must also gain at least eight replies or use at least 10% less search cost without losing any paired case total. Costs use the same sealed token rates for all arms. Case-level statistics group both repeats together.

Independent confirmation uses 24 separate cases and can only bind after development qualifies. Its exact request schedule is sealed from the selected prompt bytes and the audited development archive. The research archive records the exact responses, paired outcomes, and planned checkpoints. The GitHub repository contains the optimizer and the self-contained synthetic benchmark.

The live comparison tests GEPA selection under those three reflection configurations. OPRO and MIPROv2 informed the treatment of candidate history and the separation of proposal and validation. They have yet to be run as separate controls in this protocol. [GEPA](https://arxiv.org/abs/2507.19457) · [OPRO](https://arxiv.org/abs/2309.03409) · [MIPROv2](https://arxiv.org/abs/2406.11695)

## First live result

An offline check found that reply 10 determined the rejection under the original gate. The full experiment still dispatched all 216 qualification requests. [Early-rejection replay](typed-development-futility.md)

The GPT‑6 Luna development trial finished and replayed offline. CPO 0.2.0 and the starting prompt passed 0 of 108 holdout replies. Each GEPA control passed 1 of 108, on outage credits. Development used 491 search requests and 216 holdout requests. The failed development gate prevented independent confirmation.

CPO selected the starting prompt for every task. The search journal showed that all 12 ticket reflections omitted the canonical queue labels and that 115 validation replies across warehouse and outage had some correct fields with no exact pass. CPO 0.3.0 addresses the second problem with optional field credit. Its matched recorded-reply comparison tied the exact scoreboard and used 32 fewer search calls, with no matched critical losses. Its fresh model-backed performance remains open. [Field-aware replay](recorded-replay.md#field-aware-selection)

## Grounded follow-up

The follow-up gives every optimizer all 16 labeled training examples in each reflection and explicitly allows canonical output values. It keeps the same policies while generating fresh case facts for search, development holdout, and independent confirmation. The CPO candidate enables field credit and provides bounded excerpts and aggregate validation counts from candidate history. Final scoring remains exact. The scripted verification exercised paired scoring and checkpoint replay. [Corpus generator](../benchmarks/typed_policy.py) · [Corpus tests](../tests/test_typed_policy.py)

### Live run with a precomputed opening

The later development run gave every arm the same four labeled examples at evaluation time and used CPO’s precomputed opening pair. It stopped after 163 recorded GPT‑6 Luna replies. The shared outage opening spent its entire 1,200-token cap on reasoning and returned no usable pair. Qualification never started.

Offline replay recovered the completed ticket and warehouse searches. CPO and field-aware GEPA each passed every directly recorded matched validation case, 10 per task. Across those two tasks CPO used 50 attributed search calls and field-aware GEPA used 72, including the shared openings. The interrupted run provides search evidence on those two tasks. The held-out accuracy and independent confirmation remain unmeasured.

A separate portable fixture exercises joint and independent opening requests under recorded-style cap failures, including partial and empty opening sets. [Opening budget comparison](opening-budget.md)

### Portable grounded fixture

The public `portable-grounded-v1` protocol compares field-aware CPO with the three GEPA 0.1.4 configurations on the released typed-policy cohorts. It uses its own starting instruction and development gate. The efficiency rule counts physical search calls, including the shared opening in each arm’s attributed total. One request samples each distinct selected instruction for a case and repeat. Qualification runs after all selections finish.

Use commit `dadfd1144d650cd4374c97d7279ab08fc7915080` to reproduce the source hashes of the original fixture.

```sh
python -m pip install --require-hashes -r requirements-benchmark.txt
python -m benchmarks.grounded
python -m benchmarks.grounded --fixture --out grounded-fixture.json
python -m benchmarks.grounded --replay grounded-fixture.json
```

Preview prints the plan and its source and corpus hashes. The fixture uses a single deterministic responder for all arms. The responder uses supplied labels for ticket routing and predefined policy rules for the warehouse and outage tasks. The report records exact requests and responses, selected instructions, and scores. Replay verifies the plan, reconstructs each request against the journal, and recomputes the result.

The fixture passed 108 of 108 development replies with CPO and 36 of 108 with each GEPA control. It made 414 search calls and 216 paired holdout calls, all to the local responder. Every GEPA control solved ticket routing and stalled on warehouse and outage, where initial changes improved individual fields without making the full answer correct. This verifies the field-credit path and the comparison harness under scripted conditions. The separate sealed Luna follow-up remains the live quality test, with independent confirmation after development qualifies. [Runner](../benchmarks/grounded.py) · [Fixture](../benchmarks/grounded_fixture.py) · [Tests](../tests/test_grounded.py)

The opening and qualification comparisons also reproduce from a wheel installed in isolated Python environments. [Installed comparison verification](installed-comparison.md)

The separate staged protocol rehearses the published validation-guided repair cycle with a shared admission certificate and an independent confirmation panel. Both fixture stages replayed exactly. This version has a provider-neutral callback and awaits a separately authorized live launch. [Staged comparison and rehearsal](grounded-staged-comparison.md)
