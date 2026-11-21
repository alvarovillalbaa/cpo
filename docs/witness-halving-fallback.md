# Try halving when the witness screen has used no admission

Seven SST‑5 episodes reached the end of the witness schedule without a nominee. Successive Halving promoted a challenger in six and retained the same prompt in the seventh. Those episodes accounted for a net deficit of 121 passes. The three-admission witness arm also retained the starting prompt in all seven. The other 25 episodes passed the witness admission and gained 139 passes against cap‑8 Halving. [Original transfer](promptolution-witness-episode.md) · [Attribution](promptolution-witness-fallback-results-v1.json)

The new policy runs cap‑8 Successive Halving on the enrolled rosters in their original order when every witness cycle has declined to nominate. It uses the first halving nominee's independent proof. The original witness path keeps priority after any nomination, including a rejected proof. The replay joins identical validation observations and charges each distinct lookup once. It keeps every admission and holdout case outside search. Since each archived grade is fixed, the joined trace gives the same selections as retrieving the paid grades from a cache. [Fallback runner](../benchmarks/promptolution_witness_fallback.py)

## GSM8K and SST‑5

| Scope | Original CPO passes / lookups | With fallback | Strongest affordable control | Paired 95% range against that control |
| --- | ---: | ---: | --- | ---: |
| GSM8K | 2,473 / 711 | 2,473 / 722 | Original CPO | 0 to 0 pp |
| SST‑5 | 1,348 / 729 | 1,469 / 867 | Halving cap 12, 1,398 / 840 | +1.35 to +3.54 pp |
| Pooled | 3,821 / 1,440 | 3,942 / 1,589 | Original CPO | +1.20 to +3.06 pp |

The fallback recovered the 121-pass deficit on SST‑5. The added 138 lookups included admission, and the replay reused nine prior validation grades. It beat the strongest affordable Halving setting even after testing seven additional caps. On GSM8K the sole fallback spent 11 new lookups and retained the starting prompt. The policy failed the full gate, which requires a positive paired lower endpoint on each task and pooled against controls including the original witness rule. Both tasks use 2,880 decisions over 90 physical cases, and each bootstrap draw reselects the strongest affordable setting. [Full comparison](promptolution-witness-fallback-results-v1.json)

## BBH and LMentry transfer

The same trigger and cap replayed on all 44 archived panels using their original rotating-witness schedule, tie-extension proof, and case identities. This archive uses the earlier witness protocol. The replay reproduced all 44 published baseline pass and lookup counts. The native comparison selects from the earlier recorded GEPA grid at the fallback's realized budget. [Published native frontier](prompteval-narrow-native-admission.md) · [Transfer runner](../benchmarks/prompteval_witness_fallback.py)

| Method | Passes / 42,240 | Paid lookups |
| --- | ---: | ---: |
| Witness then Halving | 17,076 | 73,838 |
| Original one-admission witness | 16,887 | 68,125 |
| Strongest affordable GEPA, batched with 12 anchors and cap 44 | 16,180 | 71,655 |
| Cap‑8 Halving alone | 15,974 | 34,976 |

The 254 fallbacks produced 54 promotions and reused 701 lookups. BBH gained 129 passes and LMentry gained 60. The paired gain against the original witness policy was +0.45 percentage points, with a range of +0.19 to +0.75 when resampling subjects and cases together. The lead against the strongest affordable GEPA was +2.12 percentage points. That lead is a point comparison using the earlier native receipts. These are recorded-prompt selection results. The prospective Luna plan still tests the original policy, and fresh-model fallback performance remains unverified. [Transfer evidence](prompteval-witness-fallback-results-v1.json) · [Prospective plan](grounded-witness-episode.md)

## Reproduce

Use a clean checkout, Python 3.12, and GEPA 0.1.4 with the repository's pinned hash. Both replays produced byte-identical duplicates with sockets and DNS blocked. Eight targeted tests passed. Storage Guard measured 6.1 GiB free, and the temporary exports and wheel overlay used less than 0.2 GiB under the standing LAB exception. [Dependency pin](../requirements-benchmark.txt) · [Boundary tests](../tests/unit/test_promptolution_witness_fallback.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.promptolution_witness_capture --out PREDICTIONS.json
python -B -m benchmarks.promptolution_witness_fallback \
  --corpus PREDICTIONS.json \
  --execute 3c26356c2cdb562786242181e017d0b9d5dd8aeb79caebfb4576f4bc1cc729da \
  --out FALLBACK.json
python -B -m benchmarks.prompteval_witness_fallback \
  --execute 3760c4fd182f138910ff1e1eae19b2823ffb5e92d2b6f5b0e5639e618011a94a \
  --out TRANSFER.json
```
