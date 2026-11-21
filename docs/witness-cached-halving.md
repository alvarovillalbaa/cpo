# Route Halving lookahead using cached validation grades

The previous lookahead saved paid lookups in archived episodes and spent 1,024 extra reads over all 4,096 four-prompt boards with an empty cache. The new opt-in selector uses round order when the surviving four prompts and their scheduled three-case prefix have no cached grades at selection entry. A cached grade in that roster and prefix activates the published lookahead for the selection. [Earlier lookahead](witness-halving-lookahead.md) · [Selector](../cpo/halving/cached_lookahead.py)

The cold path matches every original winner and every paid request in order. Both use 24,832 total reads on the 4,096 boards, compared with 25,856 for the earlier lookahead. The exhaustive test also searches all exact decision trees over those 12 grades under a per-board cap equal to round order's observed cost. A state with different possible winners must buy another grade. A state becomes infeasible if any remaining board has reached its individual cap. The least feasible total is 24,832 reads. This establishes optimality for that cold test with the per-board constraint. [Exhaustive tests](../tests/unit/test_cached_lookahead_halving.py)

## Archived replay

At a cap of 16 new validation lookups per fallback, the cache route saved 306 paid lookups against round order and 29 against the previous lookahead. Holdout pass totals matched all three methods. Full-cap deployments and independent admission lookup counts matched round order in every episode. [Result and frozen native comparators](witness-cached-halving-results-v1.json)

| Corpus | Holdout passes | Round order paid lookups | Earlier lookahead | Cache route |
| --- | ---: | ---: | ---: | ---: |
| BBH and LMentry | 17,068 | 72,615 | 72,537 | 72,534 |
| MMLU | 30,156 | 48,322 | 48,123 | 48,097 |

At cap eight, MMLU again scored 30,159, five passes above round order. Relative to the earlier lookahead, the cache route saved 11 validation reads and spent 23 more on independent admission. The earlier and new selectors tied on holdout pass totals at every reported cap. Costs include the witness phase, fallback validation, and proof. The comparison uses fixed archived grades.

Paired resampling against the full affordable native GEPA grid confirmed the cap-16 lead on BBH and LMentry. Both MMLU cohorts still crossed zero. [Paired native comparison](witness-cached-gepa-evidence.md)

## Use

```python
from cpo.halving.cached_lookahead import CachedLookaheadHalving

search = CachedLookaheadHalving(metric_limit=16, paid=paid_validation)
nominee = search.select((incumbent, *challengers), validation_ids, evaluate)
```

Use a single search object for an episode. Its physical cap and cache carry across selections. Fresh model behavior remains unverified. The sealed model comparison uses its original round-order selector.

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel from a clean source export. Thirteen targeted tests passed with sockets and DNS blocked. The archival run reproduced all published round-order totals and the original live plan reproduced byte for byte. Storage Guard measured 5.8 GiB free. The task-owned export and wheel overlay fit the standing 0.2 GiB LAB exception and were removed. [Runner](../benchmarks/witness_cached_halving.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.witness_cached_halving
python -B -m benchmarks.witness_cached_halving \
  --execute f757fc7abd29f288b5e7d1a97dd8a98105dd900300c4b3523f81e682ed08490a \
  --out NEW_REPORT.json
```
