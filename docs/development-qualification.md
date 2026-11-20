# Stop dispatch when a development gate cannot pass

`cpo.development_qualification.run_development_qualification` takes a complete, ordered panel of physical samples and an observer. The observer scores each reply as an exact boolean. Arms sharing one physical request appear together in the sample and receive the same result. Costs passed to the gate are the already measured search costs, in the same units for every arm. [Package API](../cpo/development_qualification.py)

```python
from cpo.development_qualification import run_development_qualification

result = run_development_qualification(
    schedule,
    observe,
    gate={
        "minimumPassesPerTask": 27,
        "minimumAddedPasses": 8,
        "maxSearchCostPercentForEfficiency": 90,
    },
    search_costs=measured_search_costs,
)
```

Before each dispatch, the gate gives CPO the most favorable possible completion of the unread samples. Every unread sample that includes CPO passes and every other unread sample fails. This simultaneously maximizes CPO’s absolute scores and paired margins while preserving shared samples. If that completion fails a task floor, preservation check, or quality-or-efficiency comparison, the runner returns the observed prefix and rejection reasons. A positive decision collects the full panel. The caller owns request identity, transport, and durable persistence.

## Verification

| Case | Planned replies | Replies read by the gate | Decision |
| --- | ---: | ---: | --- |
| Portable grounded fixture | 216 | 216 | Qualified |
| Scripted ticket critical loss | 216 | 14 | Rejected |
| Every arm shares prompts at equal search cost | 108 | 0 | Rejected |
| Archived Luna v1 qualification | 216 | 10 | Rejected |

Each scripted result matched the independent full-panel verdict. The archived Luna v1 report reproduced byte for byte through the new API. That original run actually sent all 216 requests. The measured suffix contained 206 replies and $0.274521 of usage at plan rates. [Fixture results](development-qualification-results-v1.json) · [Archived Luna v1 proof](typed-development-futility.md)

## Reproduce

Use pinned GEPA 0.1.4 for the portable fixture. Preview the seal, then execute to a fresh report path.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.development_qualification
PYTHONHASHSEED=0 python -B -m benchmarks.development_qualification \
  --execute 5d6ed6243205eb6f611ccf8fc94c7e33615dae228483ccd4d925d30ddd5ee5c5 \
  --out NEW_REPORT.json
```

Nine focused tests passed, including exhaustive checks of the proof on a small shared panel. Two source-export replays matched byte for byte with sockets and DNS blocked. The CLI rejected a wrong seal and refused an existing report path. Storage Guard measured 20.8 GiB free, and the 15.5 MB temporary overlay was removed under the standing LAB exception. Fresh-model qualification remains pending. [Runner tests](../tests/unit/test_development_qualification.py)
