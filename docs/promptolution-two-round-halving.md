# Keep both challengers through the second halving round

With two challengers, the packaged halving screen cuts the roster after one shared validation case. The six- and fourteen-lookup quotes can fund a second case for the runner-up while preserving the original panel depth. This policy moves the shortlist cut to the second case when the quote covers every possible read. It keeps roster order as the tiebreaker, requires a strict validation gain, and uses the original disjoint qualification. Critical panels and quotes that cannot fund the extra reply use the original screen. [Earlier read-order replay](promptolution-settled-episode-read-order.md) · [Benchmark](../benchmarks/promptolution_two_round_halving.py)

| Variant | Packaged passes / lookups | Two-round passes / lookups | Episodes with changed decisions |
| --- | ---: | ---: | ---: |
| Settled CPO | 3,924 / 2,455 | 3,924 / 2,476 | 3 of 64 |
| Feedback CPO | 3,885 / 2,348 | 3,872 / 2,360 | 3 of 64 |

All changed episodes were on GSM8K. The settled variant reproduced every final prompt. The feedback variant changed one. In episode `47139`, the extra round nominated AdalFlow in cycle one. Qualification rejected it, and the existing feedback rule skipped cycle two. With packaged feedback, cycle one had no nominee and cycle two promoted DSPy-GEPA. This one changed path explains all 13 lost passes. The paired 95% range against packaged feedback was −0.36 to −0.09 percentage points, resampling the archived cases under the fixed episode assignments. [Cycle transitions and paired results](promptolution-two-round-halving-v1.json)

Both variants still exceed the best affordable fixed GEPA settings. At their realized costs, settled is 22 passes ahead of the native GEPA hindsight ceiling, and feedback is 30 behind. The broader hindsight menu exceeds both variants. The comparison supports keeping the packaged cut and identifies a case where rejecting a newly available finalist suppresses a later useful search. The same 64 archived episodes informed the design and evaluation. Live superiority remains unverified.

## Reproduce offline

Use the pinned Promptolution corpus and the hash-verified GEPA 0.1.4 environment from the original transfer.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.promptolution_two_round_halving \
  --corpus PREDICTIONS.json \
  --execute 2937920d5d5c11e6a9d0ec3f2b5e003b2a89552dd53a3785cb2d4a3a10edecf1 \
  --out /tmp/promptolution-two-round-halving.json
```

Two network-disabled replays produced byte-identical receipts. All 87 focused tests passed, including the recovered-tie fixture, all 4,096 four-row Boolean panels against eager two-round selection, and the original screen fallbacks. Storage Guard measured 6.5 GiB free. The task used the standing 0.2 GiB LAB exception for the disposable source, pinned wheel overlay, corpus copy, and publication checkout. Teardown was verified. [Tests](../tests/unit/test_promptolution_two_round_halving.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
