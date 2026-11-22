# Run the threshold precheck before certificate search

`run_threshold_prechecked_cycle` accepts the same fixed candidate pool, disjoint validation and qualification panels, and callbacks as the original cycle. Use it to check whether a required qualification gain is still attainable before buying validation replies. [Public API](../cpo/threshold_prechecked_cycle.py) · [Callback contract](prechecked-certificate-cycle.md)

```python
from cpo.threshold_prechecked_cycle import run_threshold_prechecked_cycle

result = run_threshold_prechecked_cycle(
    incumbent,
    candidates,
    validation_rows,
    qualification_rows,
    evaluate,
    metric_limit=13,
    qualify=qualify,
    minimum_gain=2,
)
```

The precheck reads the incumbent’s qualification cases in order. Each recorded pass lowers the maximum possible net gain by one. The cycle retains the incumbent as soon as that upper bound falls below `minimum_gain`. Once it records `minimum_gain` misses, the original validation screen can proceed. Independent qualification credits every paid incumbent reply and retains its existing family and critical-case checks. The qualification cap stays at two replies per case. A one-gain call uses the original callback sequence.

## Archived results

Across 102 model panels and 32 schedules per panel, the threshold precheck preserved every deployed prompt and held-out score for both tested margins. All 3,264 one-gain paths matched the original callback sequence. The two-gain results cover the same 3,264 paths. [Replay receipt](threshold-prechecked-cycle-replay-results-v1.json)

| Two-gain cohort | Original lookups | Threshold precheck lookups | Searches skipped | Cheaper paths | Dearer paths |
| --- | ---: | ---: | ---: | ---: | ---: |
| BBH | 12,402 | 12,107 | 104 | 129 | 591 |
| LMentry | 7,051 | 6,911 | 52 | 71 | 319 |
| Disjoint MMLU | 9,395 | 7,110 | 313 | 578 | 327 |
| Earlier MMLU | 10,001 | 7,746 | 292 | 461 | 362 |
| Total | 38,849 | 33,874 | 761 | 1,239 | 1,599 |

The precheck saved 7,362 validation lookups and added 2,387 qualification lookups, for a net reduction of 4,975 lookups (12.8%). Its cost depends on how often the incumbent rules out the requested gain early and on the relative price of the two callbacks. These are recorded lookups from fixed candidate pools. Fresh-model performance and dollar savings remain unverified.

The same precheck also reduced search cost on many native GEPA settings. The matched study compares both CPO margins against the expanded GEPA frontier at their realized lookup budgets. [Matched GEPA results](threshold-precheck-gepa-frontier.md)

## Reproduce the archived paths

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.threshold_prechecked_cycle_replay
PYTHONHASHSEED=0 python -B -m benchmarks.threshold_prechecked_cycle_replay \
  --execute 131a9233d0a23622cfbcf91dc1ddf3b0f3a0c8cbc1311a98c8345e18b60c827f \
  --out NEW_REPORT.json
```

The replay checked all 6,528 paths against the original paid callback fingerprints. The clean source export and the independently installed wheel produced byte-identical reports with SHA-256 `a24018a237cb8ffec3341a3cbba52a62db0068710d836885565c3f19fea21c02`. The installed replay placed the archived inputs and benchmark beside the installed package to preserve the original path layout. DNS and outbound sockets were blocked for both runs. The source suite passed 33 tests and 21 subtests. The installed wheel passed both new API tests and the CLI rejected the predecessor seal. The temporary work fit the standing 0.2 GiB LAB storage exception. [Replay driver](../benchmarks/threshold_prechecked_cycle_replay.py) · [API tests](../tests/test_threshold_prechecked_cycle.py)
