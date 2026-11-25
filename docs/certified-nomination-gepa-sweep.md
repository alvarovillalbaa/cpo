# Stress-test certified nomination against a denser native GEPA menu

This replay keeps the packaged paid-rate CPO policy, both archived corpora, the two-challenger rosters, and the original case splits. It expands native GEPA from 11 to 128 settings using one to six validation cases, reflection minibatches of one or two cases, and both sequential and batched search. The original controls and qualification rules carry over. The runner checks that their previous totals, the CPO totals, and the math episode layouts reproduce. [Original comparison](validation-routed-nominee-certificate.md) · [Runner](../benchmarks/certified_nomination_gepa_sweep.py)

The original reserve prices a whole native round before it can run. The budget sweep uses one representative below the first funded round and covers every integer charge from the first sequential round to the complete two-proposal quote. The batched schedule funds either no round or its one complete round. Above the complete quote, both proposals fit. The original high-cap anchors remain in the menu. A focused test compared the representatives with the exact paid traces at every eligible integer cap through 32 on seeded test panels.

Each comparison uses realized search and qualification lookups, plus historical ARC-AGI evaluator prices as a separate accounting basis. It reselects the best affordable control in each paired case resample. The sweep can identify a stronger fixed GEPA setting on these archives. Live proposal generation remains outside this replay. [Sealed receipt](certified-nomination-gepa-sweep-v1.json)

## Results

Across 760 archived AIME and ARC-AGI episodes, the table shows held-out passes followed by paid lookups. The last column gives the paired 95% case-bootstrap range for CPO minus expanded native GEPA, in passes.

| Archive | CPO | Earlier native GEPA | Expanded native GEPA | Paired 95% range |
| --- | ---: | ---: | ---: | ---: |
| AIME original | 498 / 592 | 501 / 377 | 501 / 175 | −15 to +4 |
| AIME rotated | 4,072 / 4,550 | 4,071 / 3,803 | 4,072 / 3,337 | −55 to +40 |
| ARC-AGI original | 1,432 / 678 | 1,231 / 622 | 1,341 / 644 | +55 to +127 |
| ARC-AGI rotated | 13,580 / 3,035 | 13,411 / 2,425 | 13,461 / 2,766 | +79 to +159 |

On rotated AIME, GEPA matched CPO with 1,213 fewer lookups. On ARC-AGI, the stronger controls narrowed CPO's gains to 91 and 119 passes. Matching on historical evaluator prices selected the same point controls, priced at $59.93 and $356.20 against CPO's $68.41 and $397.01. The paired ranges at those price ceilings were +55 to +126 and +79 to +159 passes.

Across 64 archived Promptolution episodes, CPO led expanded native GEPA on both GSM8K and SST5. GSM8K gained 130 passes with a paired range of +2.50 to +6.53 percentage points. SST5 gained 93 passes with a range of +1.08 to +5.07 points. Halving was the strongest affordable control on both tasks. Against halving, CPO gained 49 passes on GSM8K (+0.69 to +2.67 points) and 36 on SST5 (−0.07 to +2.50 points).

With a single setting across both Promptolution tasks, CPO recorded 3,879 passes at 2,336 lookups. Native GEPA reached 3,565 at 2,148 and halving reached 3,820 at 2,011. The paired range against halving was +0.26 to +1.79 percentage points. A post hoc comparison using the same pooled budget and allowing a different fixed setting per task raised native GEPA to 3,681 passes at 2,268 lookups. Halving still reached 3,820 at 2,011. This last comparison uses point totals from the receipt.

## Reproduce offline

Use Python 3.12, the pinned GEPA 0.1.4 wheel, and the original Promptolution corpus. Run without arguments to preview the seal.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.certified_nomination_gepa_sweep \
  --corpus PATH_TO_PINNED_PROMPTOLUTION_CORPUS \
  --execute 7f822efb38293acfcc8f34da2fb607cd0a922eae9769167169038ab29c48fd17 \
  --out NEW_REPORT.json
```

Both full replays ran with sockets blocked and produced byte-identical JSON with SHA-256 `d266328c7d95fdcfcea5dfa3bc9b0339a898dac59a195051d8fea5ade156d629`. The focused suite passed 20 tests and four subtests. The scratch workspace measured 124 MiB after both replays.
