# Tune and audit CPO search budgets on disjoint archive cases

The previous [lookup frontier](recorded-math-router-frontier.md) selected settings on the same holdout it reported. This study tests whether those settings transfer across cases. It keeps the archived candidate pools, all 40 seeds, original and rotated starting prompts, and rosters of four and eight challengers. The calibration menus include the frozen router, paired certificate, fitted fixed screen, and strict CPO. They compare against split-safe native GEPA in two modes with six qualification wrappers, uniform scoring, successive halving, and free incumbent retention. [Runner](../benchmarks/recorded_math_budget_crossfit.py)

Each archive was divided into two fixed folds by sorting a hash of the case identity. ARC-AGI uses the archived problem IDs and AIME uses its fixed source order. Each direction picks one setting per menu and budget using only grades and charges from its calibration fold. Only those named settings run on the other fold. Each fold has separate episode training, validation, qualification, and scoring roles. Validation and qualification keep their original widths. Halving training leaves 17 scoring rows per episode in each ARC-AGI fold and seven or eight on AIME.

Every method has the same hard per-episode total lookup ceilings. Each ceiling includes the configured search allowance and a reserve of two lookups per qualification row. The search allowances are 19, the integer midpoint, and the full incumbent-plus-challenger validation matrix. Calibration selects the most held-out passes among funded settings, breaking ties by realized spend and setting name. Audit results report actual paid lookups, which can differ between methods under the same ceiling. The benchmark directly replays each chosen setting on calibration to check its scored passes and spend, then checks the audit path's actual charge against its bound.

The bootstrap resamples per-case paired differences inside each audit fold. The two directions can choose different settings. Their combined range is conditional on the chosen settings and fixed partition. All cases and candidate prompts come from the previously used archives.

## ARC-AGI audit results

Each result gives held-out passes and actual paid lookups summed across both audit folds. The lookup ceiling applies per episode. The two folds provide 1,360 scoring opportunities for each root setting and 12,240 for each rotated setting at every ceiling.

| Start and challengers | Lookup ceiling | CPO | GEPA | Simple |
| --- | ---: | ---: | ---: | ---: |
| Root, four | 31 | 1,023 / 1,759 | 974 / 1,666 | 1,030 / 2,076 |
| Root, four | 41 | 1,081 / 2,474 | 1,022 / 2,344 | 1,099 / 2,736 |
| Root, four | 52 | 1,097 / 2,680 | 1,040 / 3,134 | 1,095 / 3,329 |
| Root, eight | 31 | 1,023 / 1,759 | 974 / 1,666 | 1,030 / 2,076 |
| Root, eight | 57 | 1,095 / 2,976 | 1,040 / 3,134 | 1,095 / 3,329 |
| Root, eight | 84 | 1,101 / 3,065 | 1,073 / 4,236 | 1,097 / 4,605 |
| Rotated, four | 31 | 9,525 / 10,160 | 9,412 / 8,318 | 9,598 / 14,209 |
| Rotated, four | 41 | 9,639 / 15,887 | 9,526 / 13,865 | 9,615 / 16,640 |
| Rotated, four | 52 | 9,637 / 16,085 | 9,503 / 16,373 | 9,650 / 25,679 |
| Rotated, eight | 31 | 9,525 / 10,328 | 9,412 / 8,318 | 9,544 / 13,795 |
| Rotated, eight | 57 | 9,698 / 20,146 | 9,515 / 17,369 | 9,659 / 28,015 |
| Rotated, eight | 84 | 9,698 / 20,146 | 9,540 / 21,276 | 9,680 / 42,647 |

CPO scored more passes than GEPA at all 12 ceilings, with a positive lower endpoint in all 12 paired 95% ranges. It also cost less in five of those comparisons. Against the simple control, CPO had a positive paired range at the two rotated middle ceilings, with score gains of 24 and 39 and lookup savings of 753 and 7,869. The simple control had a positive paired advantage at the four-challenger root middle ceiling and both rotated low ceilings, spending 262 to 4,049 more lookups in those comparisons. The other seven ranges against the simple control included zero.

Calibration selected the paired certificate at the lowest ceiling in both root settings. On rotated starts it selected strict CPO in one direction and the fitted fixed screen in the other. Strict CPO was selected in both directions at every middle and high ceiling. The previous winner at the lowest realized prices, the frozen router, was never selected on ARC-AGI under this protocol. The smaller training panels and per-episode ceilings also changed, so the replay cannot isolate the impact of separating calibration from audit.

## AIME audit results

All paired ranges against both controls included zero. CPO lost four or five passes to GEPA at the root across the tested ceilings, while spending less. The rotations had descriptive CPO gains of 15–34 passes over GEPA. The largest gain used 1,203 additional lookups under the lowest eight-challenger ceiling. CPO used fewer lookups at both middle and high ceilings for both roster sizes. The audit shows an unresolved tradeoff on AIME and a remaining quality gap against simple search at low caps on ARC-AGI.

## Reproduce offline

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Omit `--execute` and `--out` to preview the seal. [Benchmark requirements](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.recorded_math_budget_crossfit \
  --group rotated --width 8 \
  --execute 997694a18a79b85b9fcc35d9c0c59c40d07d7448c305df0b77cd9faf1ebf416a \
  --out NEW_REPORT.json
```

[Root, four](recorded-math-budget-crossfit-root-4-v1.json) · [Root, eight](recorded-math-budget-crossfit-root-8-v1.json) · [Rotated, four](recorded-math-budget-crossfit-rotated-4-v1.json) · [Rotated, eight](recorded-math-budget-crossfit-rotated-8-v1.json)

Sixteen targeted tests passed. The CLI rejected an incorrect seal before creating an output. Two replays per configuration matched byte for byte across 3,040 audit episodes with DNS and outbound sockets blocked. The study issued zero provider requests. Storage Guard measured 10.0 GiB free. The temporary source export, wheel overlay and publication checkout occupied about 106 MiB under the standing 0.2 GiB LAB exception. [Targeted tests](../tests/unit/test_recorded_math_budget_crossfit.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
