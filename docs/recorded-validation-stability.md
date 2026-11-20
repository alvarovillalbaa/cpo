# Protect validation gains before qualification

The training check recovered AIME holdout passes after strict CPO promoted fragile candidates. Checking one alternate added lookups. This replay tests whether the existing validation panel can give enough protection without buying a separate training check. It keeps the ARC-AGI and AIME archives, original and rotated starts, seeds, four- and eight-challenger rosters, 180-lookup search ceiling, and disjoint qualification and holdout cases. [Training backup study](recorded-training-backup.md) · [Replay runner](../benchmarks/recorded_validation_stability.py)

## Policies

- **Strict** ranks candidates by total validation passes and requires a strict gain over the incumbent.
- **Split veto** runs that race and retains the incumbent if the leader loses net passes within either of two equal validation halves.
- **Split race** considers the same requirement while searching. It can reject a contender as soon as the paid validation replies show that one half cannot match the incumbent. This lets the best eligible contender qualify even when the overall validation leader fails the split requirement.
- **Row race** requires a challenger to keep every incumbent validation pass and add at least one. Each validation case acts as its own group.

The groups follow the seeded validation order. Both guarded races preserve the incumbent's measured critical passes and choose the highest exact score among eligible challengers evaluated within budget. Roster order breaks ties. Each challenger must have enough budget for a complete check before starting. The qualification panel still sees only one selected challenger. The GEPA comparisons apply the paid incumbent qualification precheck to CPO and both controls. The precheck can skip search when the incumbent already passes the entire qualification panel. [Frozen source data and split construction](recorded-math-validation-ties.md)

## Results

Each cell shows holdout passes / paid lookups. The table covers rotated incumbents with eight challengers.

| Policy | AIME | ARC-AGI |
| --- | ---: | ---: |
| Retain start | 4,056 / 0 | 12,944 / 0 |
| Strict with precheck | 4,002 / 10,959 | 13,932 / 8,422 |
| Split veto with precheck | 4,002 / 10,883 | 13,932 / 8,422 |
| Split race with precheck | 4,001 / 10,920 | 13,932 / 8,433 |
| Row race with precheck | 3,998 / 10,890 | 13,904 / 8,425 |
| Certified training backup with precheck | 4,073 / 12,534 | 13,822 / 10,589 |
| Batched GEPA with precheck | 4,055 / 13,410 | 13,781 / 10,785 |
| Sequential GEPA with precheck | 4,074 / 13,720 | 13,785 / 11,962 |

On AIME, the split race nominated 217 challengers and promoted 64, compared with 224 and 66 for strict with the same precheck. It saved 39 lookups and lost one pass. Its joint paired case sensitivity range against GEPA was −118 to −33, compared with −23 to +22 for the certified training backup. The row race passed fewer held-out cases than strict. At four challengers with rotated incumbents, the split race met the lookup-savings threshold against both GEPA modes and missed the quality threshold. On the original AIME root, retaining the start scored 500 and exceeded every searched arm at both widths.

On ARC with eight challengers, the strict CPO precheck saved 1,961 lookups with identical deployments in all 360 paired trials. Strict with precheck led both matched GEPA controls by at least 147 passes and cleared the gate. It saved 21.9% of lookups against batched GEPA and 29.6% against sequential GEPA, with a joint paired range of +52 to +241. The split race added 11 lookups and delivered the same score. The row race lost 28 passes. The ARC four-challenger split race led both GEPA modes on quality, with a joint range of +39 to +214. Its 7.1% saving against batched GEPA fell below the 10% requirement. [Full paired ranges, promotion counts, and historical ARC costs](recorded-validation-stability-results-v1.json)

The validation-only safeguards deliver little of the AIME benefit of reading separate training cases. Strict CPO with the shared precheck is the strongest observed setting on the eight-challenger ARC rotation. These replays reuse stored outcomes and seeded case splits. Fresh-model qualification remains pending.

## Reproduce

Use GEPA 0.1.4 and the bundled archives. Preview the seal, then execute to a fresh report path.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.recorded_validation_stability
PYTHONHASHSEED=0 python -B -m benchmarks.recorded_validation_stability \
  --execute a82528da4c0e71807ab0591e7956c7fbb6c33ad66549377c07a1aa95862541c5 \
  --out NEW_REPORT.json
```

Two source-export replays matched byte for byte with sockets and DNS blocked. Each reproduced 40 published control traces and verified that the strict precheck preserved deployments across all 1,520 paired trials. Six focused tests passed, including a comparison with exhaustive ranking on all 4,096 binary response matrices for a four-case, two-challenger pool. The CLI rejected a wrong seal and refused to overwrite an existing report. Storage Guard measured 16.3 GiB free. The bounded 15.3 MB overlay used the standing LAB exception and was removed after verification. [Focused tests](../tests/unit/test_recorded_validation_stability.py)
