# Critical-case coverage in validation panels

During the previous search study, the combined continuation lost 464 critical holdout cases that ordinary GEPA passed. In 276 of those cases, the validation panel lacked that risk type. The other 188 occurred on represented types. This study tested whether distributing validation across known risk types reduces those losses. [Previous experiment](component-spare-validation.md)

`cpo.validation.sample_validation_panel` selects a seeded, fixed-size panel with an exact critical-case quota. Callers can supply a mapping from critical row ID to a risk group. The sampler visits every group before repeating one. The quota can also be used without stratification to compare the effect of case coverage at the same budget. [Panel sampler](../cpo/validation.py)

## Experiment

The benchmark tested 32 new seeds across four deterministic profiles at evaluation caps of 96 and 144. Within each trial, every arm used the same training rows and held-out rows. Validation had 12 rows. The alternate panels sampled from the original validation rows and six additional validation-only draws. A fixture-defined risk group paired the operation family with its legacy or interaction label.

- **Original** used the unmodified validation panel.
- **Matched** sampled a new panel with the original number of critical rows.
- **Stratified** used the matched quota and the same ordinary rows, with broader coverage among critical rows.
- **Six critical** selected six ordinary rows and six stratified critical rows. The fixed quota covered all declared risk types in these trials.

CPO and both official GEPA 0.1.4 controls searched each panel with the same dependency-aware proposer. The controls ran with and without native merge. Search did not use holdout results. The known and unknown routing profiles share their case inputs so they can isolate dependency declarations.

## Results

The first two columns report CPO outcomes. Loss columns count critical holdout passes from GEPA’s original-panel arm that CPO missed. Every CPO policy scored 9,216 held-out cases.

| Validation panel | Exact passes | Search calls | Losses on missing types | Losses on represented types | Total critical losses |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original | 6,607 | 25,903 | 166 | 230 | 396 |
| Matched | 6,629 | 25,851 | 122 | 220 | 342 |
| Stratified | 6,557 | 25,806 | 32 | 284 | 316 |
| Six critical | 6,663 | 26,345 | 0 | 188 | 188 |

Stratifying under the same quota lowered missing-type losses by 90 while increasing represented-type losses by 64. The six-critical panel eliminated missing-type losses. It also eliminated approval’s matched critical losses against both GEPA controls on the same panels, but trailed both controls in approval exact passes. Routing still had matched critical losses. All four CPO policies cleared both controls on local cases.

An after-the-fact check enumerated all 27 programs allowed by the fixture. On 61 of 256 trials, no program could improve on the original-panel GEPA winner’s total while preserving every critical case it passed. The other 195 trials had room to improve. This check used the holdout only to measure the fixture’s quality ceiling after selection. It cannot identify a deployable winner.

The coverage experiment supports using risk strata to reduce blind spots. It leaves selection trade-offs on already represented cases open. The cost and qualification breakdowns include the same-panel GEPA comparisons for the primary comparison and per-arm outcomes. [Sealed results](component-risk-coverage-results-v1.json)

## Reproduce

```sh
python -m pip install --require-hashes -r requirements-benchmark.txt
PYTHONHASHSEED=0 python -m benchmarks.component_risk_coverage
PYTHONHASHSEED=0 python -m benchmarks.component_risk_coverage --execute PLAN_SHA256 --out result.json
```

Use the seal printed by the preview. The full output includes the held-out comparisons, risk attribution, and quality ceiling for each trial. Both runs used deterministic responses with DNS and outbound sockets blocked.
