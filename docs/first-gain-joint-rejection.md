# Combine terminal validation and qualification evidence

A terminal CPO cycle can retain its incumbent as soon as every challenger has a paid rejection certificate. Validation rules out a challenger when its maximum possible full-panel score ties or trails the incumbent's observed passes. Independent qualification can rule out a different challenger by the same bound on its own panel. The replay applies this rule only to the terminal uniform screen, with two challengers, three to six funded validation cases, and four noncritical qualification cases from one family. [Runner](../benchmarks/first_gain_joint_rejection.py) · [Previous qualification-only replay](first-gain-precheck-stopping.md)

The original screen orders the first four or seven validation grades, including any funded grades from the opening. Before its next lookup, a planner can pay for independent qualification grades on challengers still eligible on validation. Its correlated grade prior uses weight five for unanimous cases, with an estimated handoff cost of eight or twelve lookups. Measured grades alone establish the certificate. If the planner hands off, the original validation order and nomination resume, and the normal qualification gate reuses any grades already paid for. The receipt checks every deployment, every preceding cycle, and every previous cost and control point across 824 archived episodes. [Sealed replay receipt](first-gain-joint-rejection-v1.json)

## Results

Each cell counts paid lookups. The primary setting previews four grades and prices handoff at eight lookups. Each group reproduced its prior held-out pass count.

| Archive | Packaged baseline | Prior correlated, 12 | Four, eight | Four, twelve | Seven, eight | Seven, twelve |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| AIME original | 552 | 497 | 535 | 516 | 544 | 540 |
| AIME rotated | 4,282 | 3,808 | 4,020 | 3,990 | 4,154 | 4,190 |
| ARC-AGI original | 614 | 622 | 616 | 622 | 616 | 622 |
| ARC-AGI rotated | 2,987 | 2,775 | 2,879 | 2,873 | 2,959 | 2,980 |
| Promptolution GSM8K | 786 | 796 | 798 | 800 | 796 | 798 |
| Promptolution SST-5 | 1,392 | 1,340 | 1,375 | 1,364 | 1,384 | 1,382 |
| **Total** | **10,613** | **9,838** | **10,223** | **10,165** | **10,453** | **10,512** |

The primary setting traded 645 fewer validation lookups for 255 more qualification lookups relative to the packaged baseline. The best new setting used 327 more total lookups than the earlier correlated twelve-lookup policy, at the same 23,473 held-out passes. On rotated ARC-AGI it reached 13,578 passes in 2,873 lookups. The strongest affordable native GEPA point recorded 13,461 passes in 2,766 lookups, and the earlier CPO policy needed 2,775. On rotated AIME the new setting used 3,990 lookups for 4,080 passes. The strongest affordable native GEPA point used 3,337 for 4,072 passes. On original AIME, native GEPA and halving both retained their advantages in score and lookups. The receipt uses published native GEPA and halving points at each realized budget. The earlier correlated policy retains the best aggregate cost in this archive. Fresh proposal quality and independent live qualification remain open.

## Reproduce offline

Use Python 3.12, GEPA 0.1.4 and the pinned reduced Promptolution corpus referenced by the receipt. Run without arguments to print the plan seal.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.first_gain_joint_rejection \
  --corpus PATH_TO_PINNED_PROMPTOLUTION_CORPUS \
  --execute bc5f002f5ff88de70b504797ea5ef51f17b1e6ef5103701f46c379d5387fc673 \
  --out NEW_REPORT.json
```

Two runs with socket and DNS creation blocked produced byte-identical receipts at SHA-256 `48fbed4ec045f685653f0989a67f837963fe72caf3e3414cd211ba8cae4868c1`. All 26 focused tests passed. The new tests check all 4,096 four-case grading boards with no validation rejection and with either challenger rejected by validation. The CLI refused a stale seal, an occupied output path, and a changed corpus. Storage Guard measured 8.4 GiB free. The tracked source export, verified GEPA wheel overlay, and publication worktree were scoped to 0.15 GiB under the standing LAB exception. The replay sent zero provider requests. [Tests](../tests/unit/test_first_gain_joint_rejection.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
