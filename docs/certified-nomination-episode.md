# Use certified nomination in validation-routed CPO

`run_certified_nomination_episode` is an opt-in variant of the validation-routed episode API. It uses the same `EpisodeCycle`, `Observation`, and qualification callbacks. The caller supplies the ordered challenger rosters and disjoint validation and qualification cases. [Implementation](../cpo/full_roster_precheck/certified_nomination.py) · [Original routing API](validation-routed-episode.md)

```python
from cpo.full_roster_precheck.certified_nomination import run_certified_nomination_episode

result = run_certified_nomination_episode(
    incumbent, cycles, evaluate, qualify=qualify,
)
```

For a noncritical uniform screen with two challengers and three to six funded cases, exact bounds can settle the full-panel nominee before both full scores are known. The incumbent keeps its place on a tie, and the earlier challenger wins ties between challengers. The existing independent qualification gate evaluates the nominee. Paid validation counts guide the order of qualification reads. Pass `use_validation_rates=False` to start those reads from neutral estimates. Both settings require stable replies. The episode still reports the actual schedule, finalist, deployment, and lookup counts, including opening replies that the screen did not reuse.

Unroutable openings start with uniform as in the original API. Wider rosters, protected validation cases, unsupported depths, and other schedules retain their existing screens. The function validates the complete layout before any callback. Each deployment still requires independent qualification. [Focused package tests](../tests/unit/test_certified_nomination_episode.py)

The package replay compares each of the two settings with its benchmark implementation across 824 archived episodes. It requires the exact same ordered callback ledger, cycle transitions, outcomes, and full benchmark receipt. The paid-rate setting saved 502 lookups over ordinary routing in that benchmark, and the neutral setting saved 509. These savings are from recorded replies. [Benchmark and limits](validation-routed-nominee-certificate.md) · [Package parity receipt](certified-nomination-api-parity-v1.json)

## Reproduce offline

Use Python 3.12, the pinned GEPA 0.1.4 wheel, and the archived Promptolution corpus. Run without arguments to preview the seal.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.certified_nomination_api_parity \
  --corpus PATH_TO_PINNED_PROMPTOLUTION_CORPUS \
  --execute 7733293c7c35cf8407850b0a3490fcf1feb507bf9a3a3b1fa0290e773f3bf637 \
  --out NEW_REPORT.json
```

The source run and the run importing CPO from a locally built wheel produced byte-identical receipts at SHA-256 `3f634014c9dd4edb9c4676ad0d3734493a22c5e7bfda7f05faf5fba90c0ddcaf`. All 65 focused tests and four subtests passed, including the original routing package and prospective protocol checks. The parity CLI refused a stale seal and an existing output path. Both replays blocked sockets and sent zero provider requests. Storage Guard measured 9.0 GiB free. The source export, pinned dependency overlay, wheel build, and publication worktree used 127 MiB under the standing LAB exception. [Verification runner](../benchmarks/certified_nomination_api_parity.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
