# Policy coverage in the sealed witness comparison

Six of the 24 warehouse regimes occur in neither development scoring nor independent confirmation. A candidate can return the wrong action on any one of those regimes and still tie an exact control on both panels. The audit constructs an eight-row alternative warehouse confirmation panel that closes all six gaps across the two phases while preserving the number of critical cases and the tier and site counts. [Reproducible result and case facts](grounded-witness-regime-coverage-results-v1.json)

| Task | Generator regimes | Development | Confirmation | Missed by both | Fresh cases for complete confirmation coverage |
| --- | ---: | ---: | ---: | ---: | ---: |
| Ticket | 8 | 8 | 8 | 0 | 0 |
| Warehouse | 24 | 18 | 8 | 6 | 16 |
| Outage | 16 | 16 | 8 | 0 | 8 |

A regime is a ticket topic, a warehouse stock-sign/inspection/tier/site combination, or an outage duration/plan/cap/evidence combination from the generator. The audit reads those fields from each actual case. Each warehouse opening gets 16 regimes. The full validation pool includes all 24, while native GEPA's configured validation anchors and each admission panel include eight. The counts describe cases available to each selector. The selectors can evaluate fewer cases.

The audit changes one output field on one regime at a time, scores every reply with the sealed exact grader, and reuses the original gates. It fixes the candidate's cost at the qualifying efficiency threshold and compares against an exact control or one with the same error. Against an exact control the original confirmation missed 16 warehouse and eight outage errors because those regimes were absent. With shared errors, all 48 single-regime faults qualified on the existing confirmation. A single faulty regime still left enough correct cases to meet the task floors. The paired gate measures comparative improvement, while absolute correctness on the stress cases measures coverage. These are deliberate synthetic faults. [Audit and gate checks](../benchmarks/witness_regime_coverage.py) · [Tests](../tests/unit/test_witness_regime_coverage.py)

The eight-row alternative replaces six warehouse rows with synthetic cases from the missing regimes. All 24 warehouse errors are then detectable by an exact control in development or confirmation. Separately, the result contains 24 fresh stress cases covering every regime missing from the original confirmation alone. Those cases share no exact facts with the sealed witness or its two predecessor corpora. The sealed experiment retains its original panels. The alternative and the supplemental stress cases are offline evidence with no provider calls.

A separate confirmation rehearsal binds the eight-row alternative to the original qualifying development archive. It caught a warehouse error shared by all arms at the same 128-request ceiling. [Confirmation rehearsal](grounded-witness-warehouse-confirmation.md)

## Reproduce

Use a clean source export with the sealed files and hash-pinned GEPA 0.1.4. Two offline runs produced identical receipts. Six targeted tests passed with sockets and DNS blocked. Storage Guard measured 5.9 GiB free. The task-owned overlays used the standing 0.2 GiB LAB exception and were removed.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.witness_regime_coverage
```
