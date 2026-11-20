# Build joint prompt candidates with broader training coverage

The critical-case replay found 22 outage panels where no program in the fixed instruction and demonstration pool could satisfy the coverage gate. This experiment changes the demonstration choices while preserving the instruction proposals, bundle sizes, candidate budgets, and independent qualification. [Earlier full-pool audit](joint-risk-coverage.md)

`cpo.demonstrations.stratified_demo_bundles` accepts training case IDs and caller-declared input strata. It visits different groups before taking a second case from any group. It draws repeats from the largest remaining groups to preserve scarce cases for later bundles. The returned bundles are disjoint and deterministic for a given seed and input order. [Package API](../cpo/demonstrations.py)

## Protocol

The earlier pool crosses the instructions with an empty bundle and three random disjoint bundles of four examples. The balanced pool uses the same dimensions and instructions and instead chooses the three bundles with training input strata. It uses the declared applicability features of the fixture. Those features also govern when the scripted responder can copy a demonstrated field. The selector receives no validation or holdout outcomes and does not inspect training labels.

Both pools run the original joint sampler and its diverse-prefix coverage variant. Official sequential and batched GEPA run on both pools at the same search caps. The original 12 seeds are repeated and six additional seeds use the same policy generator. Exhaustive validation scores are computed after each replay to count eligible programs. They stay outside the optimizer's evidence and charged lookup totals. [Runner](../benchmarks/joint_demo_bundles.py)

## Results

The cap-72 comparison covers 54 task panels and 972 held-out cases.

| Selection method and demonstration pool | Holdout passes | Paid lookups |
| --- | ---: | ---: |
| Hybrid, random | 935 | 3,281 |
| Hybrid with coverage rule, random | 720 | 3,078 |
| Hybrid, stratified | 972 | 2,959 |
| Hybrid with coverage rule, stratified | 972 | 2,766 |
| Batched GEPA, stratified | 944 | 3,000 |
| Sequential GEPA, stratified | 964 | 2,810 |

The full-pool audit found a coverage-eligible program on **18 of 18** outage panels with stratified bundles, up from **four of 18** with random bundles. At cap 72, the hybrid with the coverage rule passed all 972 held-out cases. It gained 28 passes and saved 234 lookups against batched GEPA, and gained eight passes and saved 44 lookups against sequential GEPA. Both comparisons used the same stratified pool and had zero matched critical losses. The coverage rule saved 193 lookups over the hybrid with the same bundles and ordinary validation.

On the six additional seeds alone, the guarded hybrid passed 324 of 324 cases, compared with 304 for batched GEPA and 320 for sequential GEPA. It used 894 lookups, compared with 987 and 952. At cap 48, the stratified guarded hybrid passed 954 of 972, used more lookups than both GEPA controls, and still lost 12 critical passes against each. The cap-72 result establishes that training-side bundle coverage can supply usable candidates in this fixture. The fixture uses the same declared input features to apply demonstrations, so fresh-model generalization remains unverified. [Per-panel outcomes and full-pool audit](joint-demo-bundles-results-v1.json)

## Reproduce

Use pinned GEPA 0.1.4 and Optuna 4.5.0. The [wheel receipt](joint-demo-bundles-verification-v1.json) gives the verified fingerprints.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.joint_demo_bundles
PYTHONHASHSEED=0 python -B -m benchmarks.joint_demo_bundles \
  --execute 7a33d9dd7352ed3f3d109f966f7b1229e9d629662ff748ac3d6bc7b166d41da8 \
  --out NEW_REPORT.json
```

Two source-export replays matched byte for byte with sockets and DNS blocked. They reproduced 288 published random-bundle control traces. Eight focused tests passed, including scarce-stratum preservation, disjoint bundles, and training-input-only selection. The CLI rejected a wrong seal and refused to overwrite an existing result. Storage Guard measured 20.0 GiB free. The 30.2 MB temporary source and wheel overlay was removed under the standing LAB exception. [Focused tests](../tests/unit/test_demonstrations.py)
