# Compare the opening screen on typed policy tasks

The installed opening-screen API reproduced the archived binary decisions. This comparison exercises it on ticket routing, warehouse release, and outage credits, where a partially correct output can still miss a required field. It uses six existing seeded fixture cohorts and the same scripted opening and demonstration bundle for all search arms. Adaptive CPO and both official GEPA 0.1.4 modes can also request field repairs from observed training errors. [Opening-screen API](opening-screen-cycle.md) · [Seeded feedback fixture](feedback-budget.md) · [Benchmark runner](../benchmarks/opening_screen_typed.py)

Search uses 12 validation cases. The opt-in API screens eight of them and completes validation on the finalist. CPO uses field credit in search. Both GEPA modes give exact matches precedence and use matched fields to resolve partial progress. Every nominee faces the same independent eight-case qualification panel with two repeated replies per side. Qualification protects incumbent critical passes and requires nonnegative gain by family, using ticket channel, warehouse site, and outage plan as the families. A separate 18-case holdout supplies the final exact scores.

Call counts charge each search and qualification reply, one shared opening to each search arm, and every later proposal. The primary search cap is 56 lookups per panel. The gate requires preservation of every matched panel and critical pass, at least 14 of 18 exact passes per panel, and either eight additional exact passes at equal or lower cost or at least 10% fewer calls.

## Results

| Method | Cap 40 passes / calls | Cap 56 passes / calls |
| --- | ---: | ---: |
| Retain start | 24 / 0 | 24 / 0 |
| Opening screen | 297 / 970 | 297 / 970 |
| Adaptive CPO | 305 / 1,022 | 324 / 1,122 |
| Sequential GEPA | 287 / 1,029 | 314 / 1,198 |
| Batched GEPA | 24 / 234 | 287 / 1,229 |

At cap 56, the opening screen used 228 fewer calls than sequential GEPA and scored 17 fewer passes. It lost 24 matched critical passes across seven panels and missed the gate. Against batched GEPA it gained ten passes and saved 259 calls. Its weakest panel scored ten passes, below the 14-pass floor. The cap-40 batched adapter retained the start because its budget check could fund the initial 12-case validation and fell short of the 32 calls reserved for a two-proposal round.

The opening screen promoted its nominee on all 18 panels. Its seven imperfect panels came from the six outage panels and one warehouse panel. The fixture’s chosen outage prompt omitted the explicit `reason` rule, accounting for 19 missed exact passes. The warehouse prompt omitted the explicit `windowHours` rule, accounting for another eight. The demonstration bundle covered some cases for both fields. Adaptive CPO reached all 324 exact passes and used 76 fewer calls than sequential GEPA and 107 fewer than batched GEPA on this fixture. The result favors retaining a path to later field repairs for typed tasks. [Panel decisions, costs, and journals](opening-screen-typed-results-v1.json)

The follow-up reserved one later repair when the opening’s full validation showed errors. [Staged repair benchmark](opening-screen-repair.md)

## Reproduce offline

Use pinned GEPA 0.1.4 and a fresh output path.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.opening_screen_typed
PYTHONHASHSEED=0 python -B -m benchmarks.opening_screen_typed \
  --execute 692ff1582a37b6605ea9f17aea8da81ab07dd3d41fef8e8b43b04fd162c27094 \
  --out NEW_REPORT.json
```

Two clean source replays blocked sockets and DNS and matched byte for byte. Each checked 36 typed panel settings and 72 official GEPA paths. Twelve focused tests passed. The CLI rejected a stale seal and preserved an existing report. Storage Guard measured 4.7 GiB free. The 28.4 MB scratch export was removed under the standing LAB exception. This is scripted fixture evidence. Live typed proposal quality and provider costs remain unmeasured. [Verification receipt](opening-screen-typed-verification-v1.json) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
