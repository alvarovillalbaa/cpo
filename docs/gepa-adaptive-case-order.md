# Reorder GEPA proof cases after each paid grade

The optional `adaptive_case_order` setting recomputes how many winner sets remain possible on each unread validation case after every paid grade. It reads from the case with the largest remaining count. Ties use validation order. The certificate still requires every possible frontier and pruning outcome to choose the same parent and advance GEPA 0.1.4's random generator to the same state. [Selector](../cpo/gepa_frontier.py) · [Public replay](recorded-arc-adaptive-case-order-results-v1.json)

| Replay | Budget | Validation order | Adaptive order | Held-out passes per arm |
| --- | ---: | ---: | ---: | ---: |
| Width-two typed fixture | 76 reads | 1,157 | 1,090 | 622 |
| Recorded Sol | 40 reads | 4,064 | 4,080 | 380 |
| Recorded Sol | 56 reads | 4,388 | 4,380 | 380 |

The typed fixture's earlier static uncertainty order used 1,126 reads at cap 76. Adaptive ordering saved another 36. The settings below cap 76 produced the same fixture counts. All 960 recorded Sol paths kept the same parents, minibatches, proposals, admissions, and held-out grades. At cap 56, total recorded cost fell from $47.562048 to $47.524416. At cap 40, it rose from $42.628008 to $42.738144. [Sol aggregate receipt](recorded-sol-adaptive-case-order-summary-v1.json)

The 800 ARC paths kept the same schedules, admissions, and held-out grades. Adaptive ordering added two reads and $0.291842 in pooled evaluation cost at three settings. At 32 evaluation quotes with the four-quote proposal price, the read count tied and evaluation cost rose by $0.0172125. The option stays off by default. These are recorded and fixture comparisons. Fresh model-backed efficiency and quality remain unmeasured.

## Reproduce the public replay

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Preview the plan from the version that added this receipt, then pass its seal and a fresh output path. [Pinned wheel](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.recorded_arc_adaptive_case_order
PYTHONHASHSEED=0 python -B -m benchmarks.recorded_arc_adaptive_case_order \
  --execute 564dacc7ffc9d31f106aa87936efe59e7e98e601c70f4063d5ba1cbc2c270918 \
  --out NEW_REPORT.json
```

## Finite-grade proof experiment

A separate experiment restricted hypothetical grades to the evaluator's finite score support. It bounded GEPA's aggregate-score pruning order and looked for one unread grade that would settle the draw for every supported result. The extra logic saved one ARC read across 800 paths and zero reads in the width-two fixture. The experiment stays available as a reproducible patch. [Experiment patch](../benchmarks/experiments/finite-grade-frontier-v1.patch) · [Experiment receipt](recorded-arc-finite-grade-bounds-results-v1.json)

In a disposable source checkout at `6b8d50713717c9af877b04690521a5a5162f7566`, apply the patch from its absolute path. Use the same Python and pinned GEPA wheel as above.

```sh
git apply --check --unidiff-zero /path/to/finite-grade-frontier-v1.patch
git apply --unidiff-zero /path/to/finite-grade-frontier-v1.patch
PYTHONHASHSEED=0 python -B -m benchmarks.recorded_arc_finite_grade_bounds \
  --execute 80b8c50582bac708451c9ab8fde24102904cadf7dba025154b68622ac702586d \
  --out NEW_EXPERIMENT_REPORT.json
```
