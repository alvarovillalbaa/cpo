# Reopening earlier proposal branches

Continuous optimization can stall when an incumbent’s own descendants lack a useful challenger. The recorded archive already contained stronger branches. After checking all 12 recorded cases per task, we found two earlier outage candidates and one earlier warehouse candidate that beat the opening rewrite while preserving every critical case it passed. None was reachable from the rewrite alone. The ticket rewrite already passed all 12. This full-matrix audit describes the available archive. Search and promotion never use those aggregate scores. [Archive provenance](recorded-replay.md)

## Replay

CPO and the sequential and batched official GEPA 0.1.4 controls started from the same recorded opening rewrite. The proposer used one of three policies:

- **Descendants** used the recorded proposal graph.
- **Local first** put prompts from earlier branches after the incumbent’s direct children.
- **Mixed** placed both sets of prompts in one seeded order.

Earlier prompts had to be reachable from the original archive root. The replay charged an archive lookup as a proposal slot. All arms shared a cap of 144 search evaluations and 16 proposal slots. In each of 48 fresh splits per task, three recorded cases went to training, three to validation, three to promotion, and three to the replay holdout. A challenger had to prove a strict pass gain and preserve the incumbent’s matched critical passes on the separate promotion panel. The gate charged each incumbent and challenger observation it used.

## Results

Each cell shows replay holdout passes and total charged calls. The 48 splits reuse the same 12 archived cases per task.

| Task | CPO descendants | CPO mixed | GEPA sequential mixed | GEPA batched mixed |
| --- | ---: | ---: | ---: | ---: |
| Ticket | 144 / 144 | 144 / 144 | 144 / 144 | 144 / 144 |
| Warehouse | 132 / 384 | 132 / 367 | 132 / 703 | 132 / 703 |
| Outage | 82 / 1,002 | 89 / 1,098 | 90 / 1,627 | 91 / 1,703 |

Mixed retrieval qualified eight outage challengers. Descendant-only and local-first CPO qualified none. CPO never reached the stored alternatives under local-first order in these trials. Mixed CPO gained seven outage passes over descendant-only CPO, preserved its matched critical passes, and used 96 additional calls. Against GEPA with the same mixed archive, CPO saved 529 or 605 calls and lost three matched critical outcomes against each control. The earlier branches helped both search methods, and CPO still missed the outage qualification gate under equal access.

The original provider holdout was available on both sides for 41 of 48 outage splits against sequential mixed GEPA and 39 of 48 against batched mixed GEPA. CPO trailed by 54 and 36 pass observations respectively on those matched records. These totals repeat original holdout rows across splits. The replay assesses search and promotion on stored candidates. Fresh prompt generation requires a separate live test. [Sealed results and original-holdout coverage](recorded-archive-restart-results-v1.json)

## Reproduce

Run from the CPO checkout with the sealed GEPA research archive on `PYTHONPATH`. The CLI verifies the original archive seal before it offers a new replay seal.

```sh
python -m pip install --require-hashes -r requirements-benchmark.txt
PYTHONPATH=/path/to/gepa-research PYTHONHASHSEED=0 python -m benchmarks.recorded_archive_restart
PYTHONPATH=/path/to/gepa-research PYTHONHASHSEED=0 python -m benchmarks.recorded_archive_restart \
  --execute PLAN_SHA256 --out result.json
```

Raw provider replies and matrices stay in the research archive. Two network-blocked runs produced byte-identical reports.
