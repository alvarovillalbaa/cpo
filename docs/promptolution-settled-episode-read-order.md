# Preserve validation depth and change read order

The nominal-depth replay saved 986 lookups for settled CPO and lost 201 held-out passes. To locate the changed decisions, we reapplied the shallow screen at each incumbent actually reached by packaged CPO. This holds earlier deployments fixed. It is a cycle audit, so the counts do not add up to an episode-level score effect. [Nominal-depth replay](promptolution-settled-episode-quote-depth.md)

| Original schedule | Settled deployment changes | Feedback deployment changes |
| --- | ---: | ---: |
| Uniform | 19 of 93 | 14 of 77 |
| Opening halving | 5 of 57 | 6 of 54 |
| Fitted opening repair | 0 of 42 | 1 of 53 |
| Feedback halving | — | 0 of 5 |
| **Total** | **24 of 192** | **21 of 189** |

Full depth produced 20 settled deployments that the shallow screen missed. The shallow screen produced one deployment that the full screen declined. Three more cycles deployed different challengers. The feedback counts were 18, one, and two, respectively. Skipped cycles are outside the audit.

## Read-order replay

Both variants keep the funded validation panels and exact roster tie rules. Paired halving waits for the first incumbent miss, then fixes the finalist at the original first-round cut. It defers remaining incumbent grades until the finalist loses ground or the full paired scores are needed. The uniform variant uses independent Beta(1,1) priors to estimate which next grade minimizes remaining reads. Exact score bounds decide the nominee. Full incumbent and nominee counts feed the original disjoint qualification. [Replay and halving screen](../benchmarks/promptolution_settled_episode_read_order.py) · [Uniform screen](../benchmarks/two_challenger_uniform_order.py)

| Policy | Packaged lookups | Paired halving | Expected-cost uniform | Held-out passes in every arm |
| --- | ---: | ---: | ---: | ---: |
| Settled CPO | 2,455 | 2,457 | 2,457 | 3,924 |
| Feedback CPO | 2,348 | 2,354 | 2,349 | 3,885 |

All 64 archived episodes reproduced their cycle transitions, finalists, and qualification replies in both variants. Neither read ordering reduced pooled cost. The benchmark retains the two candidate orderings for replay. The packaged policies use the original rules. The archived result leaves live superiority unverified. [Sealed receipt](promptolution-settled-episode-read-order-v1.json)

## Reproduce offline

Use the pinned Promptolution corpus and the hash-verified GEPA 0.1.4 environment from the original transfer.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.promptolution_settled_episode_read_order \
  --corpus PREDICTIONS.json \
  --execute 70b274cb3dab5602ed0017366bc89d4a495ef32178a00d5cf7f4b428743953ed \
  --out /tmp/promptolution-settled-read-order.json
```

Two replays ran with DNS and outbound socket connections blocked and produced byte-identical receipts. All 82 focused tests passed. The exhaustive checks cover all 4,096 Boolean four-row panels for the incumbent and two challengers, with multiple quotes and both original halving screens. Storage Guard measured 4.7 GiB free. The disposable source, pinned wheel overlay, corpus copy, and publication worktree used the standing 0.2 GiB LAB exception. Teardown was verified. [Tests](../tests/unit/test_promptolution_settled_episode_read_order.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
