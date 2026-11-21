# Exact paired opening cycle

Use this opt-in cycle when you already have a rewrite and a repair and want to qualify the first one that proves an exact validation gain. The search tries the rewrite first. It checks the repair only when the rewrite fails validation and the remaining budget can fund the repair proof. Both proofs reuse paid incumbent grades. The validation proof requires a strict total gain, no family regression, and no critical case lost from the incumbent.

```python
from cpo import ProposalPair
from cpo.paired_opening import run_paired_opening_cycle

result = run_paired_opening_cycle(
    incumbent,
    validation_rows,
    qualification_rows,
    evaluate,
    opening_pair=ProposalPair(rewrite, repair),
    metric_limit=3 * len(validation_rows),
    qualify=qualify,
    seed=cycle_index,
)
incumbent = result.prompt
```

Give validation and qualification disjoint `cpo.Row` IDs. The validation callback returns a `cpo.Observation` with an exact boolean `passed`. The qualification callback receives `(prompt, row, repeat)` and returns a boolean. The cycle sends at most one nominee to independent qualification. A rejection or an exhausted qualification cap keeps the incumbent. Read actual callback counts from `result.search.evaluations` and `result.qualification_evaluations`.

## Recorded evidence

The package reproduced the exact opening selections on 240 archived Sol paths. Independent admission kept the same prompt on every path and scored 382 of 480 at an estimated $20.366520. That was 13.17% below fixed-opening GEPA and 2.28% below the prior certified CPO opening. The package also matched the reference results and paid call sequence in 1,536 scripted comparisons across all binary outcomes for three prompts and three validation rows with three search caps. [Sol replay](recorded-rotating-witness-graph.md) · [Cycle tests](../tests/unit/test_paired_opening_cycle.py)

On ARC-AGI and AIME, the paired cycle used the same candidates and admission as the published controls across 760 paths. The primary cap of three reads per validation case could fund both proofs. The two smaller caps were added after examining the primary result and preserve its counts and trace hashes.

| Cohort | Prior certified CPO | Paired opening at 3× cap | Paired opening at 2.5× cap | Paired opening at 2× cap |
| --- | ---: | ---: | ---: | ---: |
| ARC original | 1,462 / $82.58 | 1,496 / $83.42 | 1,448 / $80.20 | 1,448 / $80.20 |
| ARC rotated | 13,738 / $764.75 | 13,791 / $1,061.69 | 13,730 / $798.11 | 13,704 / $763.38 |
| AIME original | 488 / 508 reads | 490 / 684 reads | 490 / 547 reads | 490 / 538 reads |
| AIME rotated | 4,044 / 4,642 reads | 4,075 / 5,597 reads | 4,070 / 4,310 reads | 4,070 / 4,185 reads |

Each cell gives held-out passes and paid cost. The full-cap paired opening beat sequential and batched GEPA on original-incumbent ARC at lower estimated cost. It needed substantially more cost than both controls on rotated ARC. Neither smaller cap preserved the full-cap ARC score gains. On rotated AIME, the 2× cap gained 26 passes and saved 457 reads against certified CPO. Fixed-rewrite GEPA still led it by three passes and 979 fewer reads. The new cycle has mixed archived transfer results. Fresh proposal quality, live performance, and actual provider spend remain unverified.

The prospective staged trial binds this cycle to the existing matched GEPA arms and an independent confirmation panel. [Prospective protocol](grounded-staged-paired-opening.md)

## Reproduce the ARC and AIME transfer

Use GEPA 0.1.4 and the historical CPO control source. The two-file overlay adds the new package API and benchmark while preserving the historical control hashes. The packaged selector and all controls use the original seeded opening pair and disjoint admission. ARC costs use recorded evaluator charges and AIME uses paid reads. The archive supplies the proposals to each arm. [Input provenance and controls](recorded-opening-dominance-transfer.md) · [Transfer receipt](recorded-paired-opening-transfer-results-v1.json)

```sh
cpo_checkout=$(pwd)
replay_dir=$(mktemp -d)
git archive 100c8697f6ed3fe3959d7c9cab91b49f9cf277f7 | tar -xf - -C "$replay_dir"
mkdir -p "$replay_dir/cpo/paired_opening"
cp "$cpo_checkout/cpo/paired_opening/__init__.py" "$replay_dir/cpo/paired_opening/"
cp "$cpo_checkout/benchmarks/recorded_paired_opening_transfer.py" "$replay_dir/benchmarks/"
(
  cd "$replay_dir" || exit
  PYTHONHASHSEED=0 python -B -m benchmarks.recorded_paired_opening_transfer \
    --execute bc89f0f1a7b9b5c1c33d48f33a410f278da8016d933d8d73a4c5da928013727e \
    --out "$cpo_checkout/NEW_REPORT.json"
)
```

Verification used DNS- and socket-blocked Python, a hash-pinned GEPA wheel, and disposable source overlays under the standing LAB exception. Storage Guard measured 8.5 GiB free, and the operation was bounded at 0.2 GiB.

The receipt SHA-256 is `d8c154968b0e031a531d3bd7887db00f83f337d6f0e75b585dba34daa2476524`.
