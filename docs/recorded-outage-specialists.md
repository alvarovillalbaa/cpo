# Reusing archived prompts for long outages

A specialist selected on four reserved cases raised CPO from 507 to 628 of 660 recorded outage passes. On the same replay, CPO beat both GEPA controls using the same specialist by 18 passes, with no matched critical losses and fewer calls. Directly deploying the archived prompt scored 660 of 660 with 12 archive lookups and no new search. Including that baseline exposes how much of the improvement the archive itself supplies. [Results and seal](recorded-outage-specialists-results-v1.json)

## Protocol

The earlier veto retained an incumbent that failed all four held-out loss observations. This follow-up uses a prior prompt that passes as the fallback for the two identified conditions, long outages with missing or posted evidence. Each condition reserves its first two original provider cases by case ID. The program chooses from the three prompts with complete historical panels. A specialist must beat the incumbent and pass both reserve cases for its condition. Routing uses the input policy fields and executes one prompt per case. Each optimizer retains its own diverse-panel selection on other cases. [Earlier veto replay](recorded-outage-witness.md)

All arms can use the same archive. One prompt qualified for both conditions and on all four cases together. The whole-prompt control uses that prompt on every case. Because this choice comes entirely from the reserve, the archive-only control skips the otherwise redundant search. Reserve cost is 12 charged lookups per method for the full study. Prior generation of the three archived prompts is a sunk cost in this replay.

## Results

Each cell reports replay passes and charged calls over 220 splits of the same 12 development-bank cases.

| Policy | CPO | Sequential GEPA | Batched GEPA |
| --- | ---: | ---: | ---: |
| Diverse panels | 507 / 6,345 | 431 / 7,270 | 432 / 7,516 |
| Same routed specialist | 628 / 6,357 | 610 / 7,282 | 610 / 7,528 |
| Replace the whole prompt after search | 660 / 6,357 | 660 / 7,282 | 660 / 7,528 |
| Reuse the archive winner directly | 660 / 12 | 660 / 12 | 660 / 12 |

The routed control cleared both recorded GEPA gates with the same specialist, including critical preservation. The archive-only prompt also passed all 14 retained provider cases outside the reserve. On the three retained long-outage cases, the specialist passed all three and the incumbent passed one. Those three cases include only one with missing evidence. The retained original bank still has missing replies for several underlying prompts chosen by ordinary search. The archived provider pairs for routing include three matched critical losses against each control, with 55 and 44 missing paired outcomes respectively. The replay win and retained archive checks describe an already studied outage bank. Fresh proposal quality and live superiority remain open.

The cross-task follow-up tests whether to reuse a qualified archived prompt before paying for search. [Archive-first qualification](recorded-archive-first.md)

## Reproduce offline

Use the source archive and pinned GEPA 0.1.4. Preview to obtain the seal, then add `--execute PLAN_SHA256 --out NEW_REPORT.json`.

```sh
PYTHONPATH=/path/to/gepa-research PYTHONHASHSEED=0 python -B -m benchmarks.recorded_outage_specialists \
  --replay FULL_PROMOTION_REPLAY.json \
  --source-plan REWRITE_FIRST_PLAN.json \
  --archive ORIGINAL_OPEN_EVALS_STUDY
```

Both offline runs reproduced the original diverse-panel totals and returned byte-identical reports. Contract tests check reserve separation, complete qualification and strict gain, routing scope, and unknown replies. [Runner](../benchmarks/recorded_outage_specialists.py) · [Tests](../tests/test_recorded_outage_specialists.py)
