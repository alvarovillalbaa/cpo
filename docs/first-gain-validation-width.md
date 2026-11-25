# Reduce the funded panel for first-gain validation

The earlier first-gain study capped the number of replies while requiring a gain on the original funded panel. This replay changes the panel itself. It uses the first one, two, or three cases of a previously funded uniform screen with two challengers and three to six cases. The pilot fixes the panel before reading its grades. The original opening probes, other schedules, separate four-case qualification, and held-out cases carry over. The opening probes remain charged when they fall outside the short panel. A challenger must prove a strict gain on the short panel before it can be nominated, and must pass independent qualification before deployment. [Read-cap study](certified-strict-gain.md) · [Earlier exact-nominee depth study](validation-routed-depth.md) · [Runner](../benchmarks/first_gain_validation_width.py)

## Archived results

Each cell gives held-out passes and the number of paid lookups. The two-case arm was the primary comparison. The replay reproduced the controls and original case layouts for all 824 episodes.

| Archive | Packaged first gain | Prior terminal rule | One case | Two cases | Three cases |
| --- | ---: | ---: | ---: | ---: | ---: |
| AIME original | 499 / 552 | 499 / 497 | 500 / 194 | 497 / 280 | 498 / 379 |
| AIME rotated | 4,080 / 4,282 | 4,080 / 3,808 | 4,051 / 1,626 | 4,056 / 2,208 | 4,069 / 2,771 |
| ARC-AGI original | 1,439 / 614 | 1,439 / 622 | 1,107 / 268 | 1,304 / 359 | 1,338 / 433 |
| ARC-AGI rotated | 13,578 / 2,987 | 13,578 / 2,775 | 13,140 / 1,888 | 13,451 / 2,211 | 13,491 / 2,374 |
| Promptolution GSM8K | 2,436 / 786 | 2,436 / 796 | 2,338 / 549 | 2,379 / 624 | 2,379 / 653 |
| Promptolution SST-5 | 1,441 / 1,392 | 1,441 / 1,340 | 1,255 / 572 | 1,368 / 772 | 1,440 / 949 |
| **Total** | **23,473 / 10,613** | **23,473 / 9,838** | **22,391 / 5,097** | **23,055 / 6,454** | **23,215 / 7,559** |

The three-case arm saved 2,279 lookups and gave up 258 passes relative to the prior terminal rule. On SST-5 it saved 391 lookups for one fewer pass. Rotated AIME matched the strongest affordable native GEPA point at 4,069 passes in 2,771 versus 2,601 lookups. Original AIME still favored native GEPA at 501 passes and 175 lookups. The one-case arm there tied free retention at 500 passes.

On rotated ARC-AGI, the three-case arm led the strongest affordable native GEPA and halving points by 105 and 75 passes at its lookup budget. It spent $308.17 at recorded evaluator prices. Under that cost ceiling, the leads were 80 and 75 passes. The earlier terminal rule reached 87 more passes and required 401 more lookups than the three-case arm. On GSM8K the three-case arm trailed affordable halving by 12 passes and used 27 more lookups. These comparisons use published control points at each realized budget. They describe the archived shared proposals and do not estimate fresh-model performance. [Sealed receipt](first-gain-validation-width-v1.json)

## Reproduce offline

Use Python 3.12, the pinned GEPA 0.1.4 wheel, and the reduced Promptolution corpus bound by the receipt. Run without arguments to print the plan seal.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.first_gain_validation_width \
  --corpus PATH_TO_PINNED_PROMPTOLUTION_CORPUS \
  --execute fa9fd08767c63f52fa5edb8d33977c9fc18ff1188fb1471cd1a8feb45c8256d4 \
  --out NEW_REPORT.json
```

Two socket- and DNS-blocked replays produced byte-identical receipts at SHA-256 `5c3db0d93b49136d74e4c792279899c61c54a7da2fb51e7f03e4438ea40cdb16`. All 30 focused tests passed. The new tests cover all Boolean grading boards on each shortened panel and a nomination that independent qualification rejects. The CLI refused a stale seal, an occupied output path, and an incorrect corpus. Storage Guard measured 8.3 GiB free. The source export, wheel overlay, and publication worktree fit the 0.15 GiB scope of this run under the standing LAB storage exception. Zero provider requests were sent. [Tests](../tests/unit/test_first_gain_validation_width.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
