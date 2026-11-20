# Reject impossible critical coverage during confirmation

The cap-48 demonstration replay missed all 18 holdout cases on warehouse seed 43063. Six candidates in the fixed pool met the complete validation gate. The search spent nine additional lookups each on two candidates that passed portions of validation but failed the group coverage rule. At cap 72 the sampler reached a subsequent proposal that passed all 12 validation cases. [Prior benchmark](joint-demo-bundles.md)

`cpo.coverage_confirmation.confirm_covered_gain` reuses cached evidence and stops when a protected case fails, the best possible score cannot beat the target, or a required risk group has no remaining case that could pass. It returns an improving score only after all validation cases have been scored. The caller reserves enough budget to finish every confirmation it starts. The coverage-first order checks protected cases first and then favors uncovered groups with fewer unobserved cases at the start of confirmation. The early-veto control uses the previous ordering with the same rejection rules. [Confirmation API](../cpo/coverage_confirmation.py)

## Results

The comparison repeated the 18 published seeds and added six untouched seeds from the same fixture generator. Each cap covers 72 task panels with 1,296 holdout observations. All arms use the same stratified demonstration pool. The two CPO variants keep the Optuna sampler, three-case screening prefix, complete nomination gate and eight independent qualification cases. Savings during confirmation can fund additional sampler trials. Paid lookups include the two shared proposal calls, search and qualification. [Runner](../benchmarks/joint_coverage_confirmation.py)

| Method | Cap 48 passes / lookups | Cap 72 passes / lookups |
| --- | ---: | ---: |
| Previous coverage gate | 1,278 / 3,567 | 1,296 / 3,597 |
| Early veto, original order | 1,296 / 3,360 | 1,296 / 3,360 |
| Early veto, coverage first | 1,296 / 3,318 | 1,296 / 3,318 |
| Batched GEPA | 1,000 / 3,376 | 1,250 / 3,974 |
| Sequential GEPA | 1,183 / 3,447 | 1,284 / 3,702 |

Both early-veto variants recovered all 18 warehouse holdout passes at cap 48. They used 39 search lookups on that panel versus 42 for the previous policy, with 17 additional lookups for qualification and the shared proposals. Across all panels, coverage-first saved another 42 lookups compared with the original order. Both early-veto variants produced identical traces across the two caps. Coverage-first had zero matched critical losses against either GEPA control.

On the six untouched seeds at cap 48, coverage-first scored 324/324 with 790 lookups. Batched GEPA scored 280/324 with 897, sequential GEPA scored 306/324 with 849, and the previous coverage gate scored 324/324 with 831. Across all seeds at cap 48, descriptive 95% paired bootstrap intervals for the lookup difference were [−280, 187] against batched GEPA and [−265, 0] against sequential GEPA. The intervals describe resampling 24 fixture seeds with all three tasks grouped together, using 10,000 draws with seed 3501. The aggregate lookup savings at cap 48 were 58 and 129, respectively. Generalization to fresh model replies remains unverified. [Matched outcomes, critical losses and lookup counts](joint-coverage-confirmation-results-v1.json)

The follow-up tested the same confirmation rule on recorded model outcomes. Early rejection improved the outage replay over the late gate, and matched critical losses against GEPA persisted. [Recorded transfer](recorded-coverage-confirmation.md)

## Reproduce

Use GEPA 0.1.4 and Optuna 4.5.0. The [verification receipt](joint-coverage-confirmation-verification-v1.json) records wheel fingerprints.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.joint_coverage_confirmation
PYTHONHASHSEED=0 python -B -m benchmarks.joint_coverage_confirmation \
  --execute 47ce5a351794495ebcf43239ecc9c7fcb585caa296a8a4bf0137e445f1f16513 \
  --out NEW_REPORT.json
```

Two exact-source replays produced identical bytes with sockets and DNS blocked. They reproduced 324 published control traces. Eleven focused tests passed, including exhaustive checks that both confirmation orders agree with the complete gate on a four-case panel. The CLI rejected a wrong seal and an existing output path. Storage Guard measured 19.3 GiB free. The 30.9 MB temporary source and wheel overlay was used under the standing LAB exception and removed. [Confirmation tests](../tests/unit/test_coverage_confirmation.py)
