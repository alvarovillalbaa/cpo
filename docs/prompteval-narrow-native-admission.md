# Compare CPO with narrower GEPA validation panels

CPO led the strongest affordable fixed GEPA setting by **1.903 percentage points** on the 44 archived BBH and LMentry panels. Batched GEPA with eight anchors and cap 32 moved the native comparison within CPO's lookup budget. It scored 38.075% with 60,211 lookups. CPO scored 39.979% with 68,125 lookups. [Sealed results](prompteval-narrow-native-admission-results-v1.json)

The earlier one-attempt comparison used 24 validation anchors for every arm. This replay keeps CPO at that operating point and also lets GEPA validate on the first 8, 12, or 16 enrolled anchors. The dataset, case identities, proposal rosters, four-cycle schedule, and independent admission and holdout are inherited. The original 24-anchor CPO and two native comparators rerun alongside the nine narrower native settings. [Parent comparison](prompteval-matched-admission-attempt.md) · [Runner](../benchmarks/prompteval_narrow_native_admission.py)

Sequential GEPA runs at caps 20 and 32 with eight anchors, 28 and 44 with 12, and 36 and 56 with 16. Batched GEPA runs at caps 32, 44, and 56 respectively. These caps cover the original native round reserve at the chosen widths. The search ends after the first admission decision, even if that admission rejects the nominee. Paid lookup counts include search cache misses and observed grades on disjoint admission cases.

The primary comparison selects the highest-scoring fixed native setting within CPO's realized lookup budget. The starting prompt is eligible at zero cost. Paired resampling keeps both models and all episodes together for each physical holdout case. Each draw reselects the strongest native setting affordable at that draw's costs. The resulting ranges account for selecting from the measured width and cap grid. This is a retrospective analysis of archived paths.

| One-attempt method | Validation anchors | Search cap | Holdout passes | Paid lookups |
| --- | ---: | ---: | ---: | ---: |
| Sequential GEPA | 8 | 20 | 15,135 | 41,423 |
| Sequential GEPA | 12 | 28 | 15,288 | 50,705 |
| Batched GEPA, strongest affordable | 8 | 32 | 16,083 | 60,211 |
| Rotating-witness CPO | 24 | 56 | 16,887 | 68,125 |
| Batched GEPA | 12 | 44 | 16,180 | 71,655 |
| Sequential GEPA | 8 | 32 | 16,616 | 76,764 |
| Batched GEPA, previous comparator | 24 | 80 | 16,367 | 103,937 |
| Sequential GEPA | 16 | 56 | 16,886 | 112,226 |

CPO gained 804 passes against the strongest affordable fixed GEPA setting, with gains of 253 on BBH and 551 on LMentry. The paired 95% range after reselecting GEPA in each draw was +1.532 to +2.277 percentage points with subjects fixed, and +0.994 to +2.723 with subjects and cases resampled. The eight-anchor batched setting was selected in 3,487 of the 4,096 joint draws. The wider sequential cap-56 setting came within one pass of CPO and used 44,101 more lookups.

The result covers the measured width and cap grid with supplied archived prompts. Fresh-model performance and live costs remain unverified.

## Reproduce

Use Python 3.12 and hash-pinned GEPA 0.1.4. The run reproduced 176 earlier panel-level score and cost records. Four panels, covering both models on the first and last archive tasks, replayed from a separate clean export with matching counts and traces for every arm. Verification blocked DNS and sockets. Storage Guard measured 4.1 GiB free, and the standing LAB exception allowed up to 0.2 GiB for disposable sources. The replay made zero new provider requests. [Benchmark requirement](../requirements-benchmark.txt) · [Focused tests](../tests/unit/test_prompteval_narrow_native_admission.py)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.prompteval_narrow_native_admission
PYTHONHASHSEED=0 python -B -m benchmarks.prompteval_narrow_native_admission \
  --execute 82a0465ee2a171e90a7cee6a3a482454a8d15c36e624ee474fe192f2c0bec6e9 \
  --out NEW_REPORT.json
```

The results SHA-256 is `16e1dc37d6a088d2b4d6f1b3cb58e4153460490d10234ddb6c5c53fc49fd7092`.
