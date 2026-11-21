# Certify the final Halving winner directly

The opt-in `LookaheadHalving` selector returns the exact winner of the existing logical cap-eight schedule. It applies the original tie order to eliminate candidates in rounds with zero scheduled reads. The 13-prompt archive schedule reduces to seven and then four prompts this way. The remaining schedule grades the first case for each prompt and ranks the two survivors on the same three-case prefix. [Existing selector](bounded-halving-fallback.md) · [Lookahead selector](../cpo/halving/lookahead.py)

The selector retains the possible binary completions of the paid validation grades. It can stop as soon as they all give the same final winner, even if they disagree on the first-round survivors. If more than 512 completions remain, it reads an unresolved first-round grade. Within that bound a memoized search excludes cells whose outcomes cannot change the winner and chooses the next grade that minimizes worst-case depth. Ties favor less work across equally weighted completions, then the enrolled cell order. Every evaluation is charged to the physical cap. If the winner remains undecided at the cap, the fallback keeps the incumbent. The independent proof and held-out rows stay outside the lookahead.

## Archived comparison

| Corpus | New validation cap per fallback | Round order, passes / paid lookups | Lookahead, passes / paid lookups |
| --- | ---: | ---: | ---: |
| BBH and LMentry | 8 | 17,027 / 70,809 | 17,027 / 70,759 |
| BBH and LMentry | 16 | 17,068 / 72,615 | 17,068 / 72,537 |
| BBH and LMentry | 32 | 17,076 / 73,126 | 17,076 / 73,074 |
| MMLU | 8 | 30,154 / 46,580 | 30,159 / 46,377 |
| MMLU | 16 | 30,156 / 48,322 | 30,156 / 48,123 |
| MMLU | 32 | 30,166 / 48,716 | 30,166 / 48,518 |

At cap 16, both selectors had the same holdout pass totals and zero difference across the paired resampling draws. At cap eight, the MMLU difference had a subject-and-case 95% interval of 0 to +0.025 percentage points. The full-cap replay reproduced every final deployment and its admission cost. The lookahead cap-16 scores were 888 passes above the best affordable recorded GEPA setting on BBH and LMentry and 29 above it on MMLU. These are comparisons against the fixed native frontier at the measured cost. The case intervals compare the two Halving read orders. [Results and comparator settings](witness-halving-lookahead-results-v1.json)

On cold binary boards, lookahead used 2,704 grades across all 512 three-prompt boards versus 2,768 for round order. Across all 4,096 four-prompt boards it used 25,856 versus 24,832. It reached the same winner on every board. These tests distinguish archived savings with preexisting grades from uniformly enumerated cold behavior. Fresh model performance remains unverified. [Boundary and parity tests](../tests/unit/test_lookahead_halving.py)

A follow-up uses round order on cold four-prompt boards and keeps lookahead for cached validation. It matched the original cold request paths and saved 29 further lookups at cap 16 on the archived comparison. [Cache-routed lookahead](witness-cached-halving.md)

## Use

```python
from cpo.halving.lookahead import LookaheadHalving

search = LookaheadHalving(metric_limit=16, paid=paid_validation)
nominee = search.select((incumbent, *challengers), validation_ids, evaluate, logical_limit=8)
```

The case order and prompt order carry their existing meanings. Calls with other logical limits, or without enough prompts or cases for the two paid rounds, use the original selector. The sealed model protocol uses the published round-order selector.

## Reproduce

Use a clean source export and the hash-pinned GEPA 0.1.4 wheel. Preview the seal, then execute with a fresh report path. Eleven focused tests passed with sockets and DNS blocked. Storage Guard measured 5.9 GiB free. Task-owned exports stayed within the standing 0.2 GiB LAB exception and were removed. [Benchmark runner](../benchmarks/witness_halving_lookahead.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.witness_halving_lookahead
python -B -m benchmarks.witness_halving_lookahead --execute PLAN_SHA256 --out NEW_REPORT.json
```
