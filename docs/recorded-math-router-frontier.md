# Primary search across lookup budgets on AIME and ARC-AGI

The [previous replay](recorded-math-router-transfer.md#backup-capacity-at-the-strict-budget) found that terminal backups recovered 19 of the 315 and 341 passes separating the ARC-AGI rotations from strict math CPO. This replay gives the primary search more room. It retains the same archived prompts, 40 seeds, original and rotated starting prompts, four- and eight-challenger rosters, and disjoint validation, qualification and holdout cases. It reuses the frozen language router and fixed screen without refitting. [Benchmark runner](../benchmarks/recorded_math_router_frontier.py)

The four CPO families are the frozen router, its fitted fixed screen, the deferred screen with paired qualification ordering, and strict math CPO. Each sweeps every integer search cap from one full validation panel through the unique incumbent-and-challenger validation matrix. That gives caps of 6–30 and 6–54 on AIME, and 8–40 and 8–72 on ARC-AGI. The original 19-read router and 180-read strict points reproduce their archived scores and charges. The paired qualification ordering and strict bounds still check the original qualification panel.

The comparison charges actual validation and qualification lookups. The two native GEPA modes use split-safe training and validation caches, full and half validation widths, every funded cap through 180, and six qualification wrappers. The simple menu uses uniform scoring and successive halving with the existing joint qualification rule. All menus include free incumbent retention. Each task and roster has three common lookup ceilings. They come from the actual 19-read router's cost, the integer midpoint, and the actual 180-read strict policy's cost.

The caps and families shown below were selected after observing the same archived holdout used for reporting. The tables describe what each menu could attain within those ceilings. The case-paired ranges keep the selected settings fixed and resample by original case ID, including across rotations. They do not account for selecting among many settings or establish performance on new problems.

## ARC-AGI

Each result gives held-out passes and paid lookups. The strongest affordable CPO arm had more passes than either affordable control in all 12 comparisons. Every case-paired range against either selected control had a positive lower endpoint.

| Start and challengers | Lookup ceiling | CPO arm and search cap | CPO | GEPA or retention | Simple or retention |
| --- | ---: | --- | ---: | ---: | ---: |
| Root, four | 582 | Router, 10 | 1,360 / 543 | 575 / 0 | 1,132 / 434 |
| Root, four | 945 | Paired certificate, 24 | 1,513 / 902 | 1,411 / 929 | 1,461 / 899 |
| Root, four | 1,308 | Strict, 32 | 1,563 / 1,274 | 1,525 / 1,195 | 1,495 / 1,150 |
| Root, eight | 636 | Router, 14 | 1,360 / 597 | 575 / 0 | 1,334 / 612 |
| Root, eight | 1,071 | Paired certificate, 28 | 1,513 / 934 | 1,411 / 929 | 1,461 / 899 |
| Root, eight | 1,507 | Strict, 49 | 1,578 / 1,499 | 1,528 / 1,311 | 1,547 / 1,477 |
| Rotated, four | 3,205 | Router, 10 | 13,563 / 3,112 | 13,315 / 2,894 | 13,274 / 2,840 |
| Rotated, four | 5,920 | Paired certificate, 23 | 13,833 / 5,913 | 13,721 / 5,725 | 13,779 / 5,661 |
| Rotated, four | 8,636 | Strict, 32 | 13,878 / 8,578 | 13,766 / 8,046 | 13,829 / 8,619 |
| Rotated, eight | 3,531 | Router, 17 | 13,591 / 3,531 | 13,486 / 3,445 | 13,274 / 2,840 |
| Rotated, eight | 6,957 | Paired certificate, 35 | 13,885 / 6,940 | 13,731 / 6,835 | 13,779 / 5,661 |
| Rotated, eight | 10,383 | Strict, 46 | 13,932 / 10,353 | 13,790 / 9,986 | 13,858 / 9,423 |

The best router scores already fit the lowest ceilings. At the middle ceiling, the paired certificate recovered 270 of the 315 missing rotated passes with four challengers and 294 of 341 with eight. In the eight-challenger rotation its paired ranges were +78 to +234 against GEPA and +59 to +155 against successive halving. The strict arm recovered the full rotated gap at both widths. The replay supports a change of primary search policy as the available budget rises. Simply raising the frozen router's cap left its best affordable scores unchanged.

## AIME

At the middle ceiling, the strict arm with a 17-read cap gave the best rotated CPO result at both widths. It scored 4,073 passes in both settings. GEPA scored 4,071 with four challengers and 4,073 with eight. At the highest ceiling, the eight-challenger GEPA alternative reached 4,081 passes. The four-challenger root matched the simple control's 501 passes using three additional lookups. With eight challengers, CPO chose free retention at 500 passes while the simple control reached 501 within each ceiling. Every AIME paired range against its selected GEPA or retention control included zero.

## Reproduce offline

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Omit `--execute` and `--out` to preview a plan's seal. [Benchmark requirements](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.recorded_math_router_frontier \
  --group rotated --width 8 \
  --execute 76336f75bb347c1a49a892103336368d5c4a35edda731067696d27e70640f2cc \
  --out NEW_REPORT.json
```

[Root, four](recorded-math-router-frontier-root-4-v1.json) · [Root, eight](recorded-math-router-frontier-root-8-v1.json) · [Rotated, four](recorded-math-router-frontier-rotated-4-v1.json) · [Rotated, eight](recorded-math-router-frontier-rotated-8-v1.json)

Twelve targeted tests passed. Two socket- and DNS-blocked replays per configuration matched byte for byte across the 1,520 archived episodes. The study dispatched zero provider requests. Storage Guard measured 10.0 GiB free. The bounded source export, pinned wheel overlay and publication checkout used the standing 0.2 GiB LAB exception. [Targeted tests](../tests/unit/test_recorded_math_router_frontier.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
