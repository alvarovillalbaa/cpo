# Screen proposals on fewer validation cases

The qualification experiments left a gap to batched GEPA. This replay changes how CPO uses its 72 search lookups. A short panel lets it score more proposals. The runner then measures the selected challenger and incumbent on every remaining validation case. Only a strict gain on all 24 cases can advance to the original independent qualification. [Previous qualification experiment](proposal-qualification-veto.md) · [Runner](../benchmarks/proposal_short_validation.py)

The short panel is the first 8, 12, or 16 cases in the original seeded validation order. The runner reserves two lookups per omitted case before search, so it can always finish the pair within the cap. It reuses replies already paid for. When the short panel selects no challenger, the reserve goes unused. Both official GEPA modes and the original CPO comparisons retain their published budgets and traces.

The primary comparison uses 12 cases on the eight additional Gemma and Falcon panels. It requires the joint paired 95% range against both GEPA modes to be above zero and paid lookups to be at or below both controls. The other widths and the earlier cohorts are exploratory. [Archive provenance](independent-mmlu-transfer.md)

## Results

| Method | Development passes / lookups | Earlier transfer passes / lookups | Additional archive passes / lookups |
| --- | ---: | ---: | ---: |
| Original cap-72 CPO | 4,159 / 33,177 | 10,237 / 66,831 | 9,000 / 66,958 |
| 8-case screen | 4,165 / 32,701 | 10,252 / 65,203 | 9,019 / 66,069 |
| 12-case screen | 4,185 / 32,699 | 10,234 / 66,408 | 8,989 / 64,903 |
| 16-case screen | 4,163 / 31,911 | 10,245 / 64,663 | 8,993 / 64,006 |
| Sequential GEPA | 4,139 / 44,944 | 10,236 / 91,649 | 9,012 / 92,773 |
| Batched GEPA | 4,176 / 44,194 | 10,263 / 88,226 | 9,020 / 89,426 |

On the additional archive, the 12-case screen selected 718 challengers over 1,024 cycles. Completing validation rejected 300 of them before qualification. The primary screen finished 31 passes behind batched GEPA and used 24,523 fewer lookups. Its joint paired 95% range was −81 to +6 passes, so it missed the accuracy gate.

The eight-case screen finished one pass behind batched GEPA, used 23,357 fewer lookups, and had a joint paired range of −51 to +39 passes. It used 889 fewer lookups than original cap-72 CPO and called the proposal callback 1,749 times, compared with 69 calls for cap-72 CPO. The callback returns archived proposals in this benchmark. Live reflection cost would have to average below 0.53 evaluation lookups per extra callback for the lookup saving against cap-72 CPO to cover the added calls. The original search remains the default. [Panel outcomes, search counters, and paired ranges](proposal-short-validation-results-v1.json)

## Reproduce offline

Use pinned GEPA 0.1.4 and a fresh output path.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.proposal_short_validation
PYTHONHASHSEED=0 python -B -m benchmarks.proposal_short_validation \
  --execute 401bfe59d44d76ab3c940805846b4e8b6c626295f082dd6ffcf3ac3fd0a8c3ba \
  --out NEW_REPORT.json
```

Two clean source replays blocked sockets and DNS and matched byte for byte. Each exercised 7,680 experimental cycles and reproduced 80 published control traces. Eight focused tests passed, including full-panel vetoes, independent qualification, and the hard funding bound. The runner rejected a stale seal and preserved an existing report. Storage Guard measured 6.6 GiB free. The 26.8 MB scratch export was removed under the standing LAB exception. [Tests](../tests/unit/test_proposal_short_validation.py) · [Verification receipt](proposal-short-validation-verification-v1.json) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
