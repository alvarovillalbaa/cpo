# Correct GEPA cache identities and test a cheaper fixed opening

GEPA 0.1.4 numbers rows starting at zero in each list loader. Its evaluation cache keys on the prompt and row ID, and the reflective proposer writes minibatch evaluations into that same cache. With separate training and validation lists, a cached training reply can satisfy a validation lookup at the same position. A controlled test gives the rewrite zero real validation passes and the starting prompt one. Plain lists selected the rewrite after reading only two of its four validation rows. Stable case IDs read all four and retained the start. [Regression test](../tests/unit/test_gepa_disjoint_cases.py) · [Split-safe adapter](../benchmarks/gepa_disjoint_cases.py)

The same collision occurred in the retained Luna v5 journal. Each of six completed GEPA paths used two training replies to score its eventual nominee on validation. The original archive lacks the 12 corresponding validation replies. A split-safe replay diverged at request 29, and even task-scoped exact-reply reuse could complete none of the six corrected paths. The archive contains no qualification replies. [Luna prefix audit receipt](luna-v5-split-safe-prefix-reuse-v1.json)

The corrected Sol replay ran both native GEPA modes at all 53 search caps on the original 240 paths. Both CPO policies reproduced their original paths. At cap 56 the correction changed 12 sequential and 13 batched GEPA selections. The prior reports retain the original observations and pricing as historical evidence. [Corrected frontier](grounded-gepa-disjoint-frontier-results-v1.json)

| Policy | Passes out of 480 | Search reads | Estimated cost |
| --- | ---: | ---: | ---: |
| Opening-only CPO | 382 | 1,517 | $21.673896 |
| Cheapest matching split-safe native GEPA | 382 | 2,880 | $29.003640 |
| Cheapest matching fixed-opening GEPA with cached validation | 382 | 1,920 | $23.456712 |

The split-safe native match was sequential GEPA at cap 12. The separate fixed-opening control used the same validation cases for native GEPA's minibatch gate and full validation. It charged each prompt-and-case reply once and generated no new instruction from validation feedback. The replay tested minibatches of one, two, and four with either the supplied rewrite or the supplied pair. The cheapest match used the rewrite and a two-case minibatch. It preserved every matched critical pass in both directions. Opening-only CPO used 7.6% less at the recorded rates against this stronger control. [Cached-opening control](../benchmarks/gepa_cached_opening.py) · [Fixed-opening results](grounded-gepa-cached-opening-results-v1.json)

Both offline experiments reproduced byte for byte. Five focused tests passed with sockets and DNS blocked. The scoring cases and proposals come from the same retained Sol archive. The corrected native and cached-opening comparisons measure validation and cost on those fixed replies. Fresh model quality and spending remain open.

Run the controlled regression and fixed-opening lookup tests with GEPA 0.1.4 installed.

```sh
python -m pytest -q tests/unit/test_gepa_disjoint_cases.py tests/unit/test_gepa_cached_opening.py
```
