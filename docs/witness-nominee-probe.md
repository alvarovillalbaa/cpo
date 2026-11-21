# Test a matched validation probe inside the admission allowance

Ranking the existing paid grades changed only one MMLU nomination. This replay compares the original nominee with an already-evaluated rival on one shared validation case. It freezes the search prefix and nomination trigger, then tests total allowances of 16, 20, and 24 lookups. Each allowance covers both the optional probe and a single independent proof. The proof-only arm at the same cap measures the effect of the proof allowance. The 24-lookup proof-only arm reproduces original CPO. [Paid-only ranking](witness-paid-nominee-ranking.md) · [Replay runner](../benchmarks/witness_nominee_probe.py)

The rival is the already-evaluated alternative with the highest smoothed pass rate. Among shared validation cases that can show a rival win, the probe uses the case that needs the fewest new grades, breaking ties by enrolled case order. The rival must pass that case while the original nominee fails. Each new grade reduces the proof allowance by one. The selected prompt uses its own independent admission cases and the original tie-extension rule. If the exact proof reaches its cap without settling the decision, CPO retains the start. [Probe cost and boundary tests](../tests/unit/test_witness_nominee_probe.py)

The other benchmark family chooses whether to probe and how large a cap to use. It selects the highest promotion count within original proof-plus-probe spend, with lower cost breaking ties. The transferred rule must have a positive paired subject-and-case lower endpoint against original CPO and fit its realized lookup cost. Credit for the probe also requires a positive paired lower endpoint against the no-probe arm at the same cap. The replay reports the strongest archived GEPA point affordable at each observed cost.

## Results

Both training families selected the original 24-lookup proof-only policy. No transfer cleared the gate. The table reports the original and the probe arms at both ends of the tested cap range. [All six arms and paired intervals](witness-nominee-probe-results-v1.json)

| Cohort | Cap | Proof-only passes / lookups | Probe passes / lookups | Proof-only unsettled | Probe unsettled |
| --- | ---: | ---: | ---: | ---: | ---: |
| BBH and LMentry | 16 | 16,989 / 71,667 | 16,132 / 73,061 | 122 | 582 |
| BBH and LMentry | 24 | 17,068 / 72,534 | 17,057 / 74,544 | 0 | 76 |
| MMLU prior subjects | 16 | 21,150 / 33,384 | 21,142 / 33,548 | 132 | 306 |
| MMLU prior subjects | 24 | 21,180 / 34,343 | 21,168 / 34,850 | 0 | 113 |
| MMLU additional subjects | 16 | 8,984 / 13,480 | 8,971 / 13,618 | 39 | 148 |
| MMLU additional subjects | 24 | 8,976 / 13,754 | 8,987 / 14,077 | 0 | 27 |

The probe switched 32 of 539 MMLU nominees and bought 1,050 new validation grades. At cap 24 it lost one pooled pass and used 830 more total lookups than proof-only. At cap 20 it gained 14 pooled passes over the matching proof-only arm and spent 716 more lookups. The 95% paired ranges for both MMLU cohorts included zero at every cap. On BBH and LMentry, the cap-16 probe lost 857 passes against its proof-only control. Its paired range was −2.590 to −1.446 percentage points. The result records the cost of reserving room for one shared case in this proof policy. Fresh model behavior remains unverified.

Changing proof read order at cap 24 saved 1,799 lookups with the same deployments. [Budgeted admission ordering](witness-budgeted-admission.md)

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel in a clean source export. Sixteen targeted tests passed. Two offline replays produced byte-identical reports and the original plan reproduced. The CLI rejected a stale seal before creating output. Storage Guard measured 5.8 GiB free. The export and wheel overlay used the standing 0.2 GiB LAB exception and were removed.

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.witness_nominee_probe
python -B -m benchmarks.witness_nominee_probe \
  --execute 8a70b15170f1232997fcaa6ba58fe857a1d52786587557a310d5243d6f9b4746 \
  --out NEW_REPORT.json
```
