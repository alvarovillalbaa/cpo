# Stop proposal search after a validated gain

Expected-cost qualification reduced the original proposal-driven cycle's total lookups by 1.1%. The earlier budget sweep showed a larger search tradeoff. On the eight MMLU transfer panels, CPO's cap-72 setting saved 21,395 lookups compared with batched GEPA and scored 26 fewer holdout passes. This study tests whether the saved search budget is better spent on cycles that have yet to find a validated gain. [Earlier proposal replay](expected-cost-proposal-cycle.md)

Each candidate policy first runs the original proposal search with 72 lookups. It stops when the fully measured nominee is perfect on validation, or improves on the incumbent by at least one or two exact passes with no family loss. Otherwise it replays search with a 104-lookup cap. The extension reuses measured prompt and case replies and charges the union of both windows against the 104-lookup ceiling. If the union hits the ceiling before the wider search completes, the first window's nominee advances. The proposer in the archive uses a fixed stream. The replay counts each distinct reflection context once, with reflection counts reported separately from lookup cost.

Only the final nominee is eligible for promotion. It still has to pass expected-cost qualification on the original eight independent cases. Both policies use the same starts, proposal blocks, and case splits as the fixed-cap CPO and GEPA controls. The benchmark checks those controls against the previous full traces and resamples holdout cases with both model panels and all seeds paired. [Runner](../benchmarks/proposal_branch_stop.py)

## Results

| Policy | Development passes / lookups | Transfer passes / lookups |
| --- | ---: | ---: |
| CPO at cap 72 | 4,159 / 33,177 | 10,237 / 66,831 |
| CPO at cap 104 | 4,161 / 53,144 | 10,238 / 107,121 |
| Stop on one gained pass | 4,170 / 46,080 | 10,240 / 91,833 |
| Stop on two gained passes | 4,161 / 49,907 | 10,227 / 101,008 |
| Batched GEPA | 4,176 / 44,194 | 10,263 / 88,226 |
| Sequential GEPA | 4,139 / 44,944 | 10,236 / 91,649 |

On transfer, the one-pass policy extended 635 of 1,024 cycles and changed 347 nominees during the extension. It saved 15,288 lookups and gained two passes relative to cap 104. Compared with cap 72 it added 25,002 lookups and gained three passes. It used 3,607 more lookups and scored 23 fewer passes than batched GEPA. Its joint paired 95% range against both GEPA controls was −85 to +36. The two-pass rule spent more and scored lower than the one-pass rule. The observed results do not support the staged rule for the proposal cycle. [Panel results, extension counts, and paired ranges](proposal-branch-stop-results-v1.json)

## Reproduce offline

Use pinned GEPA 0.1.4 and a fresh output path.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.proposal_branch_stop
PYTHONHASHSEED=0 python -B -m benchmarks.proposal_branch_stop \
  --execute aecf7bedd131f2f06b2d42a0c8df32910baa4245c6037cb404a011d01cc81cdf \
  --out NEW_REPORT.json
```

Two independent replays matched byte for byte with sockets and DNS blocked. They verified 3,072 staged cycle paths and reproduced 48 published panel-control traces. Eight focused tests passed, including forced exhaustion of the shared lookup ceiling. The runner rejected a stale seal and preserved an existing report. Storage Guard measured 10.2 GiB free. The 26.3 MB scratch overlay was removed under the standing LAB exception. [Tests](../tests/unit/test_proposal_branch_stop.py) · [Verification receipt](proposal-branch-stop-verification-v1.json) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
