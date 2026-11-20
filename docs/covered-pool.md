# Validate a fixed prompt pool with critical coverage

`cpo.covered_pool.select_covered_pool` applies the coverage-first policy to a supplied candidate list. Put the incumbent first and put the challengers in the order they should be considered. Supply one stratum label for each critical validation row. A challenger must strictly improve the exact validation score, preserve the original incumbent's passing critical rows, and pass at least one row per represented critical stratum.

The selector reserves enough lookups for a complete confirmation before evaluating a challenger. It stops confirming as soon as the best remaining score or group coverage cannot satisfy the gate. Only a complete exact score can replace the incumbent. `PoolResult.evaluations` counts all calls to the evaluator, including the incumbent. The selector uses caller-supplied `Observation` values.

```python
from cpo.covered_pool import select_covered_pool
from cpo.paired_qualification import certify_paired_qualification

selection = select_covered_pool(
    (incumbent, *challengers),
    validation_rows,
    evaluate,
    metric_limit=36,
    critical_strata=validation_strata,
)
next_prompt = incumbent
if selection.prompt != incumbent:
    qualified = certify_paired_qualification(
        incumbent, selection.prompt, qualification_rows, qualify,
        evaluation_limit=16, seed=17,
    )
    next_prompt = qualified.prompt
```

`evaluate(prompt, row)` returns an `Observation`. `qualify(prompt, row, repeat)` returns an exact boolean. Supply independent qualification rows with disjoint IDs and keep their labels and outcomes outside candidate selection. A qualification that rejects or runs out of budget returns the incumbent. To supply demonstration options, build disjoint bundles from training input strata with `cpo.demonstrations.stratified_demo_bundles`. [Demonstration example and evidence](joint-demo-bundles.md) · [Paired qualification](paired-qualification.md)

For a validation panel with a missed case that is the only witness in its critical stratum, the optional required-probe selector checks that case first. [Opt-in API and measured trade-offs](recorded-required-probe.md)

## Verify the installed selector

From outside the checkout, install the CPO wheel and the pinned GEPA 0.1.4 wheel in an isolated Python environment. Run the verifier with `CPO_SOURCE` pointing to a checkout of this change and `GEPA_RESEARCH` pointing to the intact research directory. The recorded comparison also requires its original Open Evals archive.

```sh
python -I -B "$CPO_SOURCE/benchmarks/covered_pool_replay.py" --study-root "$GEPA_RESEARCH"
```

The verifier checks that CPO and GEPA load from the installed environment. It substitutes the public CPO selector into the archived challenge race and checks the resulting lookup counts, selection, qualification, and held-out results. Python 3.12.14 reproduced the complete published report byte for byte. Python 3.10.21 with `--allow-interpreter-drift` reproduced the original loop's complete report on that interpreter, including all 1,320 CPO selection decisions. On 3.10 each GEPA control used two extra qualification lookups per outage cap compared with the published report, with the same search lookup counts and holdout passes.

Each fresh install passed 10 focused checks, and both replays ran with socket creation and DNS blocked. Two offline builds produced byte-identical wheels. Storage Guard measured 17.0 GiB free. The 64.7 MB source and environment scratch was removed under the standing LAB exception. [Installation receipt](covered-pool-installation-v1.json)

This verifies the installed implementation against a fixed archive of provider replies. The replay's accuracy, cost and critical-case limitations still apply. [Recorded comparison](recorded-coverage-confirmation.md)
