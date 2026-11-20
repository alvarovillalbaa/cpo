# Transfer the shared challenger probe to ARC-AGI and AIME

One shared probe per challenger improved the recorded outage comparison. This replay applies the same four-candidate window to the bundled ARC-AGI and AIME score archives. The archives lack declared critical strata, so the shared probe uses the first validation case the incumbent missed. Ranking uses exact results. Every nominee still needs a fully scored validation gain and separate paired qualification. [Outage experiment](recorded-coverage-window.md) · [Score archive and provenance](recorded-math-validation-ties.md)

The experiment reuses the two search caps of 36 and 52, 40 seeded splits, rotated incumbents, and eight-challenger rosters. The **ordered control** uses the same fully scored CPO confirmation without the shared probe. Existing controls include adaptive strict CPO, posterior allocation, full-score history, Successive Halving, both official GEPA modes, and retaining the start. The precheck and lookup accounting match the prior benchmark. ARC also retains historical evaluator costs for each paid reply. [Previous allocation comparison](recorded-score-allocation.md) · [Runner](../benchmarks/recorded_window_transfer.py)

## Results

Cells show holdout passes / paid lookups.

| Archive and cap | Ordered CPO | Binary window | Posterior allocation | Batched GEPA | Sequential GEPA |
| --- | ---: | ---: | ---: | ---: | ---: |
| ARC 36 | 13,914 / 8,167 | 13,909 / 8,290 | 13,952 / 7,976 | 13,641 / 6,045 | 13,768 / 8,385 |
| ARC 52 | 13,932 / 8,730 | 13,929 / 8,744 | 13,932 / 8,128 | 13,744 / 9,517 | 13,789 / 11,169 |
| AIME 36 | 4,021 / 10,381 | 4,009 / 10,442 | 4,001 / 10,275 | 4,066 / 7,437 | 4,079 / 9,970 |
| AIME 52 | 4,002 / 11,344 | 4,003 / 11,186 | 4,002 / 10,777 | 4,065 / 12,211 | 4,074 / 13,376 |

On ARC at cap 52, the binary window improved on both GEPA controls' observed holdout scores. Its joint paired range was +52 to +231 passes, but its 8.1% savings against batched GEPA fell below the 10% requirement. Posterior allocation used 616 fewer lookups, scored three more passes, and cleared the archived gate. On AIME the window trailed both GEPA controls and retaining the start at both caps. At cap 52 its joint paired range against GEPA was −117 to −31. Resampling groups repeated observations by the original problem. [Full costs and paired ranges](recorded-window-transfer-results-v1.json)

An exhaustive diagnostic after replay found that passing the shared probe was associated with a higher chance of exact validation improvement. However, **292 of 733** ARC candidates and **440 of 842** AIME candidates with a strict full-panel gain failed that probe. Counts aggregate candidate appearances over admitted search trials. The screen can still confirm these candidates when budget remains. The transfer result supports keeping the window out of the default ordering. [Witness counts](recorded-window-transfer-results-v1.json)

A follow-up limited the probe to cases required by the coverage gate and used the ordered race on the other panels. [Required-probe replay](recorded-required-probe.md)

## Reproduce

Use pinned GEPA 0.1.4 and the bundled score archives.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.recorded_window_transfer
PYTHONHASHSEED=0 python -B -m benchmarks.recorded_window_transfer \
  --execute 4ce4282a09b525fe98202e5a9b1588bf1983a1ad1c379bd01c06af43edf02776 \
  --out NEW_REPORT.json
```

Two exact-source replays matched byte for byte with sockets and DNS blocked. They reproduced 28 published arm traces and the associated totals. Fifteen focused tests passed. The CLI rejected a wrong seal and an existing output path. Storage Guard measured 13.3 GiB free. The 19.0 MB temporary source and wheel overlay was removed under the standing LAB exception. [Verification receipt](recorded-window-transfer-verification-v1.json)
