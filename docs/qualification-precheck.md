# Skip search when qualification cannot improve the incumbent

`cpo.qualification_precheck.run_prechecked_qualification` runs an incumbent-only precheck before a supplied search. For a panel with `N` case-repeat pairs, each observed incumbent pass removes one possible gain. If fewer than the required gains remain possible, the cycle keeps the incumbent and skips the search. If the precheck observes enough incumbent misses to make the requested gain possible, it stops reading and invokes search. [Package API](../cpo/qualification_precheck.py)

```python
from cpo import select_pool
from cpo.qualification_precheck import run_prechecked_qualification

result = run_prechecked_qualification(
    incumbent,
    qualification_rows,
    nominate=lambda: select_pool(
        (incumbent, *challengers), validation_rows, evaluate,
        metric_limit=52, adaptive_rejection=True,
    ).prompt,
    qualify=qualify,
    repeats=2,
    minimum_gain=1,
    seed=17,
)
next_incumbent = result.prompt
```

Keep validation and qualification row IDs disjoint. The search callback takes no arguments and returns one prompt. The qualification callback takes a prompt, a row, and a repeat index and returns an exact boolean. The qualifier reuses the corresponding incumbent replies and still requires a strict gain, no family regression, and no loss on a critical case. The equivalence applies when a given prompt, row, and repeat produce the same outcome in either evaluation order.

`result.nominee` is `None` when search was skipped. `result.decision.observations` lists all qualification callbacks in dispatch order, including the paid precheck prefix. `result.precheck_evaluations` counts that prefix and `result.qualification_evaluations` counts the whole ledger. Meter search separately through its evaluator. The optional `evaluation_limit` applies to qualification only. A limit below the size of a complete paired panel uses the ordinary evaluation order so prepaying cannot change its decision at that cap.

## Archived verification

The public API reproduced **4,560 trial traces** across strict CPO and the two pinned GEPA modes. The replay checked every nomination, deployment, paid lookup, and recorded ARC cost. These totals show strict CPO at eight challengers. [Sealed replay results](qualification-precheck-replay-results-v1.json)

| Archive and start | Searches skipped | Paid lookups before | Paid lookups with precheck | Holdout passes |
| --- | ---: | ---: | ---: | ---: |
| ARC-AGI, original | 0 / 40 | 1,507 | 1,507 | 1,578 |
| ARC-AGI, rotated | 106 / 360 | 10,383 | 8,422 | 13,932 |
| AIME, original | 0 / 40 | 1,422 | 1,439 | 476 |
| AIME, rotated | 15 / 320 | 11,166 | 10,959 | 4,002 |

The precheck can add lookups when search finds no nominee or qualification would have resolved before reading the prepaid replies. On rotated ARC, strict CPO still cleared the archived gate with the same precheck applied to both GEPA controls. Fresh-model performance remains unverified. [Matched GEPA comparison](recorded-validation-stability.md)

## Reproduce

Use GEPA 0.1.4 and the bundled archives. Preview the seal, then execute to a fresh report path.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.qualification_precheck_replay
PYTHONHASHSEED=0 python -B -m benchmarks.qualification_precheck_replay \
  --execute bf72fd30d3ee2cabf67f939d80dbee614384c54f8bb905dda2927a5af5f5b3eb \
  --out NEW_REPORT.json
```

The source export and an offline-built wheel produced byte-identical reports with socket creation and DNS blocked. Twenty-five focused tests passed. They included 4,096 binary response matrices with repeats, critical cases, multiple families, and three gain thresholds. The CLI rejected a wrong seal and preserved an existing report. Storage Guard measured 16.3 GiB free. The 15.4 MB scratch source, wheel, and replay outputs were removed under the standing LAB exception. [Focused tests](../tests/unit/test_qualification_precheck.py)
