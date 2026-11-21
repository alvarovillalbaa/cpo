# Independent admission retry after exact rejection

Expected-read proof ordering saved 1,799 lookups in the preceding replay. This experiment tested whether a second proof could spend some of those savings on a stronger prompt. It kept the archived search, original nominee, validation reads, grading rule, and held-out cases fixed over 2,240 episodes. [Previous replay](witness-budgeted-admission.md) · [Runner](../benchmarks/witness_admission_retry.py)

After an exact rejection, the retry selects the highest smoothed validation pass rate among the other challengers with paid grades. It uses the rival's original admission panel when the full panel is available and otherwise takes the earliest full available panel. The original base panel and any used tie panel are retired in full. The rival must clear the same exact gain requirement. An undecided first proof ends the attempt. The joint cap covers both proofs, including ties. The retry starts only if the remaining allowance can pay for a minimum promotion certificate. With eight base rows and a one-win gain requirement, a first rejection needs at least eight reads and a second promotion needs at least nine. A joint cap of 16 cannot fund both.

The matched controls allow only the first proof at the same cap. On the other benchmark family, the selector maximizes promotions under the realized spend of the original seeded proof at cap 24, then minimizes proof lookups. The selected rule must show a positive lower endpoint versus full expected-read proof at cap 24 and stay within the original spend on every held-out cohort.

## Results

| Cohort | Joint cap | Retry attempts | Retry promotions | Change in holdout passes vs same-cap control | Extra paid lookups vs same-cap control | Paired 95% range, percentage points |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| BBH and LMentry | 20 | 91 | 14 | +133 | +910 | +0.147 to +0.495 |
| BBH and LMentry | 24 | 331 | 42 | +233 | +3,455 | +0.327 to +0.777 |
| MMLU prior subjects | 20 | 10 | 0 | 0 | +102 | 0 to 0 |
| MMLU prior subjects | 24 | 108 | 1 | 0 | +1,104 | −0.013 to +0.013 |
| MMLU additional subjects | 20 | 8 | 0 | 0 | +77 | 0 to 0 |
| MMLU additional subjects | 24 | 67 | 1 | −3 | +700 | −0.070 to +0.016 |

At cap 20, the BBH and LMentry retry gained 54 held-out passes over full expected-read proof at a cost of 641 extra lookups. It still spent 822 fewer lookups than the original seeded proof. On MMLU the cap-20 retry added no promotions. The cap-24 retry exceeded original seeded cost on all three cohorts and its two MMLU promotions yielded no gain in aggregate held-out passes. Both training families selected the single expected-read proof at cap 24. The retry failed the transfer gate and remains an archived experiment. [Full results](witness-admission-retry-results-v1.json)

## Reproduce

Use a clean source export, Python 3.12, and the hash-pinned GEPA 0.1.4 wheel. The two replays matched byte for byte with sockets and DNS blocked. Seventeen targeted tests passed, the CLI rejected a stale seal, and the prospective development plan reproduced byte for byte. The replay sent zero provider requests. Storage Guard measured 5.6 GiB free and the export and wheel overlay fit the standing 0.2 GiB LAB exception. [Retry tests](../tests/unit/test_witness_admission_retry.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.witness_admission_retry
python -B -m benchmarks.witness_admission_retry \
  --execute 106e4f616fb12821db8b42212e9e4eb2db10eb15b2881218bbb2b01ccc6494c1 \
  --out NEW_REPORT.json
```
