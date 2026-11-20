# Spend one repair on a typed opening with validation errors

The opening screen passed independent qualification in all 18 typed panels, yet it missed fields that adaptive search recovered. This comparison keeps the opening screen and funds one additional repair when the selected opening has exact validation misses. It uses the same fixture, demonstration bundles, search caps, and independent qualification schedule. [Typed benchmark](opening-screen-typed.md) · [Runner](../benchmarks/opening_screen_repair.py)

The staged search reserves enough budget to validate the repair on every case. It then buys up to two training probes in the primary arm or up to four in the exploratory arm. The proposer receives only those training replies. It is called only when a probe fails. A repair takes the opening’s place if it improves the exact validation score, preserves the opening’s critical passes, and preserves each family’s score. Only the final nominee can enter qualification against the original incumbent.

## Results

| Method | Cap 40 passes / calls | Cap 56 passes / calls |
| --- | ---: | ---: |
| Opening screen | 297 / 970 | 297 / 970 |
| One repair, up to two probes | 305 / 996 | 305 / 996 |
| One repair, up to four probes | 314 / 1,048 | 314 / 1,048 |
| Adaptive CPO | 305 / 1,022 | 324 / 1,122 |
| Sequential GEPA | 287 / 1,029 | 314 / 1,198 |
| Batched GEPA | 24 / 234 | 287 / 1,229 |

At cap 56, two probes recovered eight warehouse passes for 26 extra calls over the opening screen. The six outage openings all had validation errors, yet each passed both paid training probes, so the proposer stayed idle. The fixture’s legacy reason value is `DEFAULT`, while the required labels are `NEEDS_DOC`, `LONG`, and `NORMAL`. Since the opening had no explicit reason rule, its passing probes relied on the demonstration bundle to supply that field. The primary arm used 202 fewer calls than sequential GEPA and lost nine aggregate passes and 19 matched critical passes. [Fixture evaluator](../benchmarks/grounded_fixture.py) · [Demonstration handling](../benchmarks/alternative_controls.py)

Four probes found repair evidence in three outage panels. That arm tied sequential GEPA on aggregate holdout passes and used 150 fewer calls. It still lost ten matched critical passes across three outage panels. Both staged policies missed the gate against sequential GEPA. The primary result identifies observed training evidence as the constraint for this staged repair. Adaptive CPO remains the stronger tested typed route at cap 56. [Typed outcomes and lookup receipts](opening-screen-repair-results-v1.json)

## Reproduce offline

Use pinned GEPA 0.1.4 and a fresh output path.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.opening_screen_repair
PYTHONHASHSEED=0 python -B -m benchmarks.opening_screen_repair \
  --execute 1e7202063b4c153024a08cd00551f8684da043594f952e054d84cbf5ae67474f \
  --out NEW_REPORT.json
```

Two clean source replays blocked sockets and DNS and produced byte-identical reports. Each checked 36 typed panel settings and reproduced 180 published arm paths, including the keep-start reference. Eleven focused tests passed, including one final qualification, critical-pass protection, and funding before reflection. The CLI rejected a stale seal and preserved an existing report. Storage Guard measured 4.7 GiB free. The 28.6 MB scratch export was removed under the standing LAB exception. These are scripted results. Live proposal quality and costs remain unmeasured. [Tests](../tests/unit/test_opening_screen_repair.py) · [Verification receipt](opening-screen-repair-verification-v1.json) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
