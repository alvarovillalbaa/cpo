# Rehearse confirmation on the six previously missed warehouse regimes

The coverage audit found six warehouse regimes that neither sealed scoring panel exercises. The separate rehearsal replaces six warehouse confirmation cases, retains the original critical-case, tier, and site counts, and requires at least one exact candidate reply out of two on each added case. The original paired gate still determines whether the candidate improves over the controls. The additional check asks whether the candidate solves each newly represented regime at least once. [Coverage audit and cases](grounded-witness-regime-coverage.md) · [Runner](../benchmarks/witness_warehouse_confirmation.py)

The runner binds the same qualifying development archive, prompt bytes, search costs, and confirmation request ceiling. It fingerprints the substituted cases and exact request schedule and keeps ticket and outage confirmation unchanged. The original development and confirmation seals still reproduce. The alternative runner accepts offline fixtures and exact replay.

| Fixture | Paired gate | Six-case check | Overall | Scored requests |
| --- | --- | --- | --- | ---: |
| Qualifying | Pass | Pass | Pass | 128 |
| One failed repeat on a new case | Pass | Pass | Pass | 128 |
| Every arm fails both repeats on a new case | Pass | Fail | Fail | 128 |
| Scoring cannot reach the paired floor | Fail | Unmeasured | Fail | 10 |

The shared-error fixture changes only the warehouse action on one case and applies that fault to every prompt. The ordinary comparative gate still passes, while the six-case check catches the persistent error. The existing futility rule can reject before a complete panel. In that case the case-level check is unmeasured. A qualifying result requires the complete original request allowance for that archive. These fixtures measure whether the protocol can detect the stated failure. Model quality remains unverified. [Fixture plan](grounded-witness-warehouse-confirmation-plan-v1.json) · [Rehearsal receipt](grounded-witness-warehouse-confirmation-rehearsal-v1.json)

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel from a clean source export. All four archives replayed byte for byte and 13 targeted tests passed with sockets and DNS blocked. Storage Guard measured 5.9 GiB free. Task-owned overlays used the standing 0.2 GiB LAB exception and were removed.

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.grounded_witness_halving_futility \
  --fixture aae517e6c51cf57645d0f788beb8d86fcc90f59a6a91ac6f85e2c3ba64ecaea0 \
  --out development
python -B -m benchmarks.witness_warehouse_confirmation --development development
python -B -m benchmarks.witness_warehouse_confirmation --development development \
  --fixture bad8f6221aec63523bd79608566b12d6d4aba58bd1f980caeb43731474b15c12 \
  --profile shared-rule-error --out confirmation
python -B -m benchmarks.witness_warehouse_confirmation --development development \
  --replay confirmation --out confirmation-replayed
```
