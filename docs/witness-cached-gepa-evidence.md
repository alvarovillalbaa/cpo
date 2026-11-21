# Pair cache-routed CPO against affordable native GEPA

The archived cap-16 results selected an affordable GEPA setting on the observed totals. This replay reconstructs the holdout votes for CPO and every native setting in the published comparison. It checks each native panel's score, paid lookups, and recorded trace hash. It also reproduces CPO's published cap-16 totals before using the paired analysis. [Cap-16 replay](witness-cached-halving.md) · [Narrow native frontier](prompteval-narrow-native-admission.md) · [MMLU native frontier](prompteval-mmlu-witness-fallback.md)

The analysis uses 22 BBH and LMentry subjects with 11 native settings. It also uses the separate nine- and four-subject MMLU cohorts with 20 settings each. The scopes retain the original episode starts, proposal rosters, disjoint search and admission cases, and holdout. The zero-cost control retains the starting prompt.

Each of 4,096 draws samples the same held-out cases for every arm. A physical case carries both recorded model panels and every episode for the subject. Subjects have equal weight. The analysis either fixes subjects or resamples subjects and their paid lookup costs together. It picks the best fixed native setting that fits the sampled CPO cost on each draw. The gate requires a positive subject-and-case lower endpoint on each of the three cohorts. The pooled MMLU result and the hindsight per-subject allocation are diagnostics. [Runner](../benchmarks/witness_cached_gepa_evidence.py)

## Results

| Archived cohort | CPO passes / paid lookups | Best affordable GEPA on observed totals | Paired 95% range |
| --- | ---: | ---: | ---: |
| BBH and LMentry | 17,068 / 72,534 | 16,180 / 71,655 | +0.916 to +3.037 pp |
| MMLU prior transfer | 21,180 / 34,343 | 21,159 / 30,096 | −0.117 to +0.158 pp |
| MMLU additional subjects | 8,976 / 13,754 | 8,976 / 13,219 | −0.386 to +0.412 pp |
| MMLU pooled | 30,156 / 48,097 | 30,127 / 46,190 | −0.120 to +0.180 pp |

BBH and LMentry cleared the paired gate across 660 physical cases. CPO's observed equal-subject score also led the hindsight per-subject GEPA allocation by 0.682 percentage points at the same total lookup ceiling. Both MMLU cohorts continued to cross zero. The pooled MMLU hindsight allocation led CPO by 0.123 percentage points. This leaves the cross-cohort superiority gate unmet. The ranges describe resampling of fixed recorded prompts and grades. Fresh proposal quality remains unverified. [Full paired results and comparator settings](witness-cached-gepa-evidence-results-v1.json)

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel from a clean source export. Eleven targeted tests passed with DNS and sockets blocked. The design preview reproduced byte for byte, the CLI rejected a stale seal before creating output, and the original live plan reproduced byte for byte. Storage Guard measured 5.9 GiB free. The disposable export and wheel overlay fit within the standing 0.2 GiB LAB exception and were removed. [Tests](../tests/unit/test_witness_cached_gepa_evidence.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.witness_cached_gepa_evidence
python -B -m benchmarks.witness_cached_gepa_evidence \
  --execute 75fd7fd23f3d28478e7dc118606d751bc2a9aee1a2b58feafe5d3c8b0ad52a45 \
  --out NEW_REPORT.json
```
