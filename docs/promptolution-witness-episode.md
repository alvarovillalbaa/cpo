# Test one-admission CPO on GSM8K and SST‑5

The published one-admission policy beat the strongest affordable GEPA setting on both recorded tasks. The full transfer gate failed because the SST‑5 comparison against Successive Halving had a paired interval that crossed zero. The prediction archive uses Gemma 3 27B programs from CAPO, DSPy GEPA, OPRO, AdalFlow, and three unoptimized prompts. [Promptolution paper](https://aclanthology.org/2026.eacl-demo.21/) · [Pinned predictions](https://github.com/finitearth/prompt-optimization-framework-comparison/tree/6cd48d2431bb5cf796273f4ea10d3119791ec483/results_eval) · [Preceding BBH and LMentry comparison](prompteval-narrow-native-admission.md)

The replay starts from the first unoptimized prompt. A seeded order assigns the six available alternatives to three pairs. Every arm sees the same pairs, starting prompt, and case splits within each of the 32 episodes per task. The validation panel has 24 cases, and each cycle has 16 separate training cases and eight fresh admission cases. Final scoring uses a fixed 90-case holdout per task. The recorded archive supplies one grade per case and program. The one-admission rule ends search after the first nomination, even if its proof rejects the challenger. The three-admission CPO arm measures the cost of continuing.

The original comparison used GEPA validation widths of 8, 12, 16, and 24 and Successive Halving at caps of 8, 16, and 32. Every tested GEPA setting cost more than CPO. The follow-up added narrower native widths of 2, 4, and 6 with their full-round reserves, then reproduced the original methods' scores, costs, and trace hashes. The paired bootstrap resamples physical cases within each task and keeps all episodes for a case together. Each draw reselects the highest-scoring control within CPO's realized lookup budget. The prespecified gate requires a positive lower endpoint on each task and the pool. [Original results](promptolution-witness-episode-results-v1.json) · [Narrower GEPA sensitivity](promptolution-witness-small-native-results-v1.json)

| Scope | CPO passes / lookups | Strongest affordable GEPA | CPO gain vs. GEPA, paired 95% range | Strongest affordable control | CPO gain vs. that control, paired 95% range |
| --- | ---: | ---: | ---: | ---: | ---: |
| GSM8K | 2,473 / 711 | 2,310 / 698 | +163, +3.06 to +8.23 pp | 2,313 / 631 | +160, +2.99 to +8.09 pp |
| SST‑5 | 1,348 / 729 | 1,114 / 612 | +234, +4.65 to +11.60 pp | 1,330 / 637 | +18, −0.07 to +1.28 pp |
| Pooled | 3,821 / 1,440 | 3,377 / 1,422 | +444, +5.30 to +10.12 pp | 3,643 / 1,268 | +178, +1.77 to +4.43 pp |

Successive Halving at cap 8 was the strongest affordable control in all three scopes. Pooled, the strongest affordable GEPA setting was sequential with two anchors and cap 14. At wider budgets, native GEPA reached 3,961 pooled passes on 5,115 lookups, and three-admission CPO reached 3,940 on 2,835. On SST‑5, the prospective benchmark's eight-anchor sequential cap-32 GEPA arm gained 102 passes over CPO and used 641 extra lookups. These are recorded selection costs. Original prompt-generation costs and fresh model performance remain open.

A follow-up tested cap‑8 Halving only after the witness screen declined every nominee. It gained 121 passes on SST‑5 and added lookups without gains on GSM8K. [Fallback and transfer evidence](witness-halving-fallback.md)

## Reproduce

The collector downloads only the pinned public prediction CSVs, verifies each Git blob, and rebuilds the binary archive byte for byte. It retains case hashes and exact-match outcomes. Use Python 3.12 and GEPA 0.1.4 from the hashed requirements. Both sealed replays ran twice with sockets and DNS blocked. Eight targeted tests passed. Storage Guard measured 6.1 GiB free, and the disposable exports and wheel overlay fit within the standing LAB exception's 0.2 GiB verification scope. [Benchmark dependency](../requirements-benchmark.txt) · [Focused tests](../tests/unit/test_promptolution_witness_episode.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.promptolution_witness_capture --out PREDICTIONS.json
python -B -m benchmarks.promptolution_witness_episode \
  --corpus PREDICTIONS.json \
  --execute f62f8821b2e7e20a0ccbd36d9e1523ef93a57b5e7b54386784371a750bdde820 \
  --out TRANSFER.json
python -B -m benchmarks.promptolution_witness_small_native \
  --corpus PREDICTIONS.json \
  --execute 1ecbbaee864c9e381fc34c48f5bf5bbefd835fe385ab4ad144895bce5a35b8b8 \
  --out SENSITIVITY.json
```
