# Stop validation at the first certified gain

On rotated AIME, exact nominee certification matched native GEPA's score while purchasing 1,213 more lookups. On the original AIME start, it scored below retention. This experiment asks how much of that spend can be avoided by proving a full-panel gain against the incumbent and then moving directly to independent qualification. [Expanded GEPA comparison](certified-nomination-gepa-sweep.md) · [Runner](../benchmarks/certified_strict_gain.py)

The benchmark keeps the same 760 archived AIME and ARC-AGI episodes, shared ordered rosters, validation cases, four independent qualification cases, and original holdouts. It changes the uniform screen when two challengers have three to six funded validation cases. The challenger qualifies for nomination once its known passes exceed the highest score the incumbent could attain. The screen can keep the incumbent once neither challenger can prove a gain with the replies left in its allowance. The ceiling counts prepaid validation reads. The usual opening route, halving branch, and independent qualification gate carry over.

A Beta estimate for each prompt determines which prompt to read next. The planner maximizes the estimated probability of proving any strict gain within the remaining cap. It breaks ties by expected read count and roster order. Only observed validation grades certify a gain. The fixed arms allow 10, 14, or 18 reads, with 14 designated primary before replay. All prior comparator totals and episode layouts must reproduce. Each paired bootstrap draw selects the strongest affordable control again. [Sealed receipt](certified-strict-gain-v1.json)

## Results

Each entry shows held-out passes and paid lookups.

| Archive | Exact nominee | Cap 10 | Cap 14 | Cap 18 |
| --- | ---: | ---: | ---: | ---: |
| AIME original | 498 / 592 | 500 / 328 | 497 / 520 | 499 / 552 |
| AIME rotated | 4,072 / 4,550 | 4,054 / 2,565 | 4,076 / 4,022 | 4,080 / 4,282 |
| ARC-AGI original | 1,432 / 678 | 1,149 / 497 | 1,368 / 592 | 1,439 / 614 |
| ARC-AGI rotated | 13,580 / 3,035 | 13,258 / 2,489 | 13,531 / 2,994 | 13,578 / 2,987 |

On original ARC-AGI, the 18-read policy gained seven passes and saved 64 lookups against exact nomination. On rotated ARC-AGI, it lost two passes and saved 48 lookups. The paired 95% ranges against exact nomination included zero in both groups. Under the 18-read policy's realized lookup ceilings, the strongest affordable GEPA points reached 1,294 and 13,461 passes. CPO led by 145 and 117 passes, with paired ranges of +104 to +189 and +76 to +157. Against halving, the leads were 112 and 162 passes, with ranges of +80 to +145 and +120 to +204.

At recorded ARC-AGI prices, the 18-read policy cost $55.85 and $390.66 against $68.41 and $397.01 for exact nomination. Matching at these prices selected a cheaper native GEPA setting on the original start. CPO's paired ranges against the strongest native GEPA settings were +148 to +250 and +76 to +157 passes. The historical price and lookup comparisons selected the same halving settings.

On rotated AIME, the 14-read policy gained four passes and saved 528 lookups against exact nomination. It used 685 more lookups than the strongest affordable GEPA point, which scored 4,072. The paired range against that GEPA menu was −50 to +43 passes. The 18-read policy gained a further four passes for 260 additional lookups, with a range of −52 to +53 against GEPA. On original AIME, every cap trailed the strongest affordable halving point, 502 passes at 216 lookups. The tightest cap gave up 283 and 322 passes against exact nomination on ARC-AGI.

The 18-read variant improved efficiency over exact nomination on these archives while preserving the lead on ARC-AGI. AIME still favors the cheaper controls on observed quality per lookup. All methods searched the same recorded prompts. The variant remains in the benchmark pending evidence on fresh proposals and independent data.

## Reproduce offline

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Run without arguments to preview the seal.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.certified_strict_gain \
  --execute 0babd387ed50b02cd2f10ee24a1d4430899b4c44a1d2b44c2c2759994d6c4a00 \
  --out NEW_REPORT.json
```

Both complete replays blocked sockets and DNS and produced identical bytes with SHA-256 `aaed69b26e4a8fce4a66377347bb36ac9e269acdd462f447f404fd116ce748dd`. All 25 focused tests passed, including every three-case grade board under three caps. The CLI refused a stale seal and an existing output path. The replays sent zero provider requests. Storage Guard measured 8.7 GiB free, and the bounded workspace measured 125 MiB under the standing LAB exception. [Tests](../tests/unit/test_certified_strict_gain.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
