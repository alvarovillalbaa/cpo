# Test whether paid validation wins justify continuing the search

Cap 13 missed useful promotions on the archived MMLU transfer trials. Extending every trial to the full pool recovered 54 passes but spent most of the additional lookups on trials that deployed the same prompt. This replay tests two ways to extend the strict validation race before independent qualification. Both keep the same 896 seeded trials, starts, and rosters. [Cap-13 transfer and cost attribution](recorded-low-cap-mmlu-transfer.md)

The first policy extends from cap 13 to cap 54 when the first stage nominates nobody and a challenger has at least one paid head-to-head win with no net loss on the cases already compared. The second policy extends whenever the first stage nominates nobody. Both reuse the same paid ledger. Each extended path must reproduce the original full-pool result exactly, and each stopped path must reproduce the cap-13 result. Only the final nominee enters independent qualification. [Replay runner](../benchmarks/recorded_paid_validation_continuation.py)

The comparison looks for a positive point margin and a nonnegative lower paired bound against the strongest affordable control. Controls include every fixed CPO cap from 13 through 54, both original GEPA modes across all 350 settings, and retained starts. Each paired case draw reselects the strongest affordable control at the policy’s observed search-plus-qualification cost. The trials and holdout cases already appeared in the cap-13 transfer, so this comparison is exploratory.

| Policy | Held-out passes | Lookups | Best affordable control | Paired margin and 95% range |
| --- | ---: | ---: | --- | ---: |
| Continue on a paid win with no net loss | 26,614 | 10,690 | Retain starts, 26,625 at zero lookups | −11, −38 to +8 |
| Continue after every failed nomination | 26,644 | 20,238 | Fixed CPO cap 32, 26,664 at 19,964 lookups | −20, −36 to −6 |

The paid signal spent 1,094 additional lookups on 46 continuations and recovered four passes over stopping at cap 13. It reached nine of the 45 promotions available only at full cap. Continuing after every failed nomination reached 40 of those promotions and recovered 34 passes at 10,642 additional lookups. The paid-signal policy missed the gate. Fixed cap 32 matched the full-pool score with 2,539 fewer lookups on this archive. Cap 32 was selected using these results. Fresh-model superiority remains unverified. [Full results and cap points](recorded-paid-validation-continuation-results-v1.json)

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel.

Two clean-export replays with DNS and sockets blocked matched byte for byte at SHA-256 `a78ff031f6a31bbabc0a4c25ea4ccb7fe1d49cd6a367e87eb56f700eec940f91`. Seventeen targeted tests passed. Direct replay checked 84 panel endpoints and the coverage of the 45 full-pool-only promotions. The CLI rejected the predecessor seal. Storage Guard measured 2.6 GiB free. The export and publication worktree fit the standing 0.2 GiB LAB exception. The replays sent zero provider requests. [Targeted tests](../tests/unit/test_recorded_paid_validation_continuation.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.recorded_paid_validation_continuation
python -B -m benchmarks.recorded_paid_validation_continuation \
  --execute e93e9a53161abb83f170aeb84c00c41ba5c5e7e8b860b8ecef1000c3a9b36bfb \
  --out NEW_REPORT.json
```
