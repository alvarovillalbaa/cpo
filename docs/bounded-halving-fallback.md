# Certify the Halving winner within a cap on new lookups

The optional `cpo.halving.HalvingSearch` selector reproduced the full fallback's deployments and proof lookup counts on every recorded episode. It saved 712 lookups on BBH and LMentry and 18 across GSM8K and SST‑5. The package also supports tighter limits on new validation calls. [Fallback baseline](witness-halving-fallback.md) · [Selector](../cpo/halving/__init__.py) · [Sealed results](witness-fallback-caps-results-v1.json)

Ordinary Successive Halving ranks each round's cumulative scores, keeps the top half, and preserves its tie order. The new selector gives each unknown binary grade a lower bound of zero and an upper bound of one. It advances the round only when those bounds establish the same ordered survivors for every possible completion. It carries the original schedule forward, with grades skipped or reused from earlier rounds leaving the scheduled prefix intact. An episode's cap counts only newly requested grades, including failed evaluation attempts. If the next grade would exceed the cap, the fallback stops without submitting a nominee for independent proof.

## Recorded results

Figures are added passes and added lookups relative to the original one-admission witness policy. Added lookups include independent proof. The caps apply only to new fallback validation lookups per eligible episode. All caps and both variants use the original proof once they produce a nominee.

| New validation cap | BBH and LMentry, plain | BBH and LMentry, certified | SST‑5, plain | SST‑5, certified | GSM8K, plain | GSM8K, certified |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 8 | +88 / 2,585 | +140 / 2,684 | +121 / 132 | +121 / 123 | 0 / 8 | 0 / 8 |
| 12 | +156 / 3,800 | +156 / 3,754 | +121 / 136 | +121 / 123 | 0 / 11 | 0 / 8 |
| 16 | +184 / 4,778 | +181 / 4,490 | +121 / 138 | +121 / 123 | 0 / 11 | 0 / 8 |
| Full replay | +189 / 5,713 | +189 / 5,001 | +121 / 138 | +121 / 123 | 0 / 11 | 0 / 8 |

The full replay uses 32 new validation lookups per eligible episode, enough for all recorded schedules. BBH and LMentry spent the same 1,575 proof lookups in both versions. With tight caps the bound-based selector can fund proofs in additional episodes, so total paid lookups and holdout scores can move in either direction. At cap 16 the certified selector saved 288 lookups and lost three passes against plain Halving on BBH and LMentry. GSM8K still gained zero passes. These experiments use archived binary grades, and fresh-model fallback performance remains open. [Replay runner](../benchmarks/witness_fallback_caps.py)

A separate prospective plan compares the 16-lookup fallback with the original witness and GEPA arms and two Halving-only controls. [Prospective fallback comparison](grounded-witness-halving.md)

## Use the selector

Use one search object per sequential episode. Supply already observed validation grades keyed by `(prompt, case_id)` and pass candidate prompts in tie-break order. The callback returns an exact `bool` for each new grade. The returned string is the Halving winner. A return value of `None` means search stopped at the cap. On a completed path, independent qualification can evaluate a challenger on separate cases.

```python
from cpo.halving import HalvingSearch

search = HalvingSearch(metric_limit=16, paid=paid_validation)
for challengers, cases in enrolled_cycles:
    nominee = search.select((incumbent, *challengers), cases, evaluate, logical_limit=8)
    if nominee is None or nominee != incumbent:
        break
```

The `evaluations` attribute counts newly requested grades. The `observations` property returns a copy of the paid grade cache. The same instance reuses exact responses across calls.

## Reproduce

Use Python 3.12 and the repository's pinned GEPA wheel. The collector rebuilds the prior public prediction archive. Socket- and DNS-blocked replays of the score study matched byte for byte. Thirteen targeted tests passed, including exact winner and purchase parity on all 4,096 binary boards of four prompts by three rows under three cache patterns. Storage Guard measured 6.1 GiB free. The checks used the standing LAB exception for at most 0.2 GiB of disposable files. [Dependency pin](../requirements-benchmark.txt) · [Targeted tests](../tests/unit/test_witness_fallback_caps.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.promptolution_witness_capture --out PREDICTIONS.json
python -B -m benchmarks.witness_fallback_caps \
  --corpus PREDICTIONS.json \
  --execute 84ed7c0a9378b5f017c1c10c56c12bb6d92900884be930c9c27ebbeb9186c522 \
  --out BOUNDED_FALLBACK.json
```
