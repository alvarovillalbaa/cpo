# Stop a fallback comparison once it cannot qualify

The separate futility seal preserves the published fallback comparison's search, admission, scoring order, and acceptance gates. It checks whether the candidate could still qualify before each scoring call. If rejection is permanent, it writes a terminal receipt with the exact paid prefix and the first unsent request hash. A qualifying run completes the whole scoring panel. [Parent comparison](grounded-witness-halving.md) · [Development plan](grounded-witness-halving-futility-development-plan-v1.json) · [Runner](../benchmarks/grounded_witness_halving_futility.py)

Each physical reply grades one distinct prompt, case, and repeat. When multiple arms share the prompt, they share the grade. The bound assigns every unknown reply that includes the candidate a pass and every other unknown reply a fail. This maximizes the candidate's task totals, paired margins, and critical-case preservation simultaneously. Search costs are fixed before scoring and both original cost measures must qualify. The terminal receipt labels the optimistic verdict as a bound. A complete observed scorecard is written only after the whole panel has run.

| Scripted run | Scored requests | Planned scoring requests | Skipped |
| --- | ---: | ---: | ---: |
| Qualifying development | 288 | 288 | 0 |
| Rejected admission | 0 | 108 | 108 |
| Faulted development scoring | 20 | 288 | 268 |
| Qualifying confirmation | 128 | 128 | 0 |
| Faulted confirmation scoring | 10 | 128 | 118 |

The rejected-admission fixture had shared deployments that made the quality gain unreachable at its fixed search costs. Its rejection required zero scoring calls. The faulted fixtures reached an impossible task floor. Their request journals matched the original development schedule through the last paid response. Both qualifying fixtures retained their full scoring panels. Every futility archive replayed byte for byte with sockets and DNS blocked. A tampered terminal receipt failed replay. Seventeen targeted tests passed, including exhaustive completions on a small paired panel. These savings are from scripted outcomes. [Rehearsal receipt](grounded-witness-halving-futility-rehearsal-v1.json) · [Boundary tests](../tests/unit/test_grounded_witness_halving_futility.py)

## Reproduce

Use Python 3.12 and GEPA 0.1.4 from the hashed requirements. The positive development fixture can bind a disjoint confirmation. The same command supports `--profile rejected-admission` and `--profile faulted-scoring`. [GEPA pin](../requirements-benchmark.txt)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.grounded_witness_halving_futility
python -B -m benchmarks.grounded_witness_halving_futility \
  --fixture aae517e6c51cf57645d0f788beb8d86fcc90f59a6a91ac6f85e2c3ba64ecaea0 \
  --out development
python -B -m benchmarks.grounded_witness_halving_futility \
  --fixture 6d1aba91bcd5ce12f457113c85df5de3d558724cceb601b3b6251ccf74d22049 \
  --development development --profile faulted-scoring --out confirmation
python -B -m benchmarks.grounded_witness_halving_futility \
  --replay confirmation --development development --out confirmation-replay
```
