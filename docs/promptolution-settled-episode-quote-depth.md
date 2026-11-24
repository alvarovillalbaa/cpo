# Preserve the quoted validation depth on smaller rosters

The frozen settled policies were fitted with eight available challengers. The Promptolution transfer offers two in each cycle. The same lookup quote can buy more complete validation cases with fewer challengers. For example, the eight-challenger uniform quote of 18 funds two cases at nominal width and six with two challengers. This experiment limits each quoted screen to the case count funded at its nominal width. [Matched transfer](promptolution-settled-episode-transfer.md) · [Prior hindsight ceiling](promptolution-settled-episode-headroom.md)

The two variants preserve the original schedule choice, candidate order, and independent admission proof. The fixed-depth certified screen uses its existing case limit. Any critical case leaves the full validation panel available to the original protected path. The benchmark verifies every original arm's score, cost, and trace before comparing the new variants. [Benchmark](../benchmarks/promptolution_settled_episode_quote_depth.py)

## Archived result

Each entry shows held-out passes and paid lookups across the same 64 episodes.

| Scope | Settled CPO | Nominal-depth settled | Feedback CPO | Nominal-depth feedback |
| --- | ---: | ---: | ---: | ---: |
| GSM8K | 2,472 / 906 | 2,338 / 601 | 2,451 / 883 | 2,338 / 591 |
| SST‑5 | 1,452 / 1,549 | 1,385 / 868 | 1,434 / 1,465 | 1,363 / 865 |
| **Pooled** | **3,924 / 2,455** | **3,723 / 1,469** | **3,885 / 2,348** | **3,701 / 1,456** |

Preserving nominal depth saves 986 lookups and loses 201 passes for settled CPO. The paired 95% range is −4.77 to −2.17 percentage points. It saves 892 lookups and loses 184 passes for feedback CPO, with a paired range of −4.34 to −2.03 points. The ranges resample physical held-out cases within each task.

Both variants still exceed the strongest affordable fixed native GEPA settings at their lower lookup budgets. Their pooled paired ranges against the broader fixed-control menu cross zero. Both trail the per-episode native GEPA hindsight ceiling at their new budgets, by 61 passes for settled and 77 for feedback. The packaged policies retain their original roster-dependent quoting. These archive results measure selection from fixed prompts and leave live performance unverified. [Sealed replay receipt](promptolution-settled-episode-quote-depth-v1.json)

## Reproduce offline

Use the pinned Promptolution corpus and GEPA 0.1.4 environment from the original transfer.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.promptolution_settled_episode_quote_depth \
  --corpus PREDICTIONS.json \
  --execute c8b0fc6e3a1b481bc8c25f35220fb3d349f8ad8aef3772f0558d46f4005582b4 \
  --out /tmp/promptolution-settled-quote-depth.json
```

Two offline replays produced identical receipts. All 80 focused tests passed, including nominal case limits, protection of a later critical case, and exact callbacks and results at full roster width. Storage Guard measured 4.9 GiB free. The disposable source, corpus copy, wheel overlay, and publication checkout fit the standing 0.2 GiB LAB exception and were removed. No provider requests were made. [Tests](../tests/unit/test_promptolution_settled_episode_quote_depth.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
