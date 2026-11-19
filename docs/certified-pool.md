# Certified selection from a prompt pool

`select_certified_pool(candidates, validation, evaluate, metric_limit=...)` treats the first candidate as the incumbent. It evaluates the incumbent on the full validation cohort, then progressively screens challengers on common rows. Protected rows are the critical validation cases the incumbent passed. The selector checks those rows first and drops a challenger if it fails one or can no longer beat the incumbent.

A challenger qualifies when it has passed every protected row and its observed passes already exceed the incumbent’s exact total. Even if every unobserved row fails, the challenger still wins on that fixed validation set. The result reports `lower_pass_bound`, `upper_pass_bound`, and `evaluations`. Equal bounds give the exact validation total. A strict improvement certificate applies to the selected challenger and incumbent on this panel. Qualification on a separate holdout is still needed before deployment.

The recorded-model comparison used the same pool sizes, 55% lookup caps, and uniform and Successive Halving adapters as the original fixed-pool benchmark. It repeated the 40 phase-three seeds and added 40 new seeds on each matrix. Cases can recur between splits because both groups use the same matrices. The matrices supply binary scores without critical labels. Exhaustive unit cases verify the critical-pass protection separately. [Original protocol and data sources](fixed-pool.md)

## Results

Each cell reports aggregate exact holdout passes and validation lookups.

| Dataset and seeds | Certified CPO | Uniform | Successive Halving | Cleared both external gates |
| --- | ---: | ---: | ---: | --- |
| Abstract algebra, phase three | 912 / 5,170 | 917 / 6,760 | 932 / 5,320 | No |
| Abstract algebra, fresh | 908 / 5,194 | 906 / 6,760 | 906 / 5,320 | Yes |
| AIME, phase three | 706 / 1,602 | 696 / 1,800 | 689 / 1,520 | No |
| AIME, fresh | 696 / 1,555 | 702 / 1,800 | 688 / 1,520 | No |
| ARC-AGI, phase three | 2,174 / 2,190 | 2,166 / 2,800 | 2,144 / 2,200 | Yes |
| ARC-AGI, fresh | 2,185 / 2,292 | 2,146 / 2,800 | 2,177 / 2,200 | No |

The gate requires no aggregate holdout loss, no added lookups, and either more passes or at least 10% fewer lookups. The selector stopped with a strict validation certificate and unevaluated rows on 26 of 240 splits. It missed the combined gate across datasets and remains opt-in. The replay makes no new model calls.

## Reproduce

Use the same recorded matrix as the original benchmark. The command previews the source, data, and seed hashes and requires that exact seal before it writes results.

```sh
python -m benchmarks.certified_pool --dataset arc-agi --matrix MATRIX_PATH
python -m benchmarks.certified_pool --dataset arc-agi --matrix MATRIX_PATH --execute PLAN_SHA256 --out result.json
```

The result includes the selected candidate, score bounds, lookup digest, and holdout total for every split. It preserves negative comparisons against both external controls and prior CPO selectors. [Selector](../cpo/certified_pool.py) · [Replay driver](../benchmarks/certified_pool.py) · [Contract tests](../tests/test_certified_pool.py)
