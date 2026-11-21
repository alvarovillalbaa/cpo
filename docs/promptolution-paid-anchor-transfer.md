# Transfer the fixed eight-lookup fallback to Promptolution

The fixed four-anchor fallback gained passes at lower lookup cost on the archived MMLU cohorts. This replay applies the same cap and nomination rule to GSM8K and SST‑5 on the recorded Gemma 3 27B archive. It uses the existing 32 episodes and 90 held-out cases per task, without fitting a rule to either task. [Fixed-cap comparison on MMLU](witness-paid-anchor-proof-fit.md) · [Promptolution archive and split](promptolution-witness-episode.md) · [Replay runner](../benchmarks/promptolution_paid_anchor_transfer.py)

Both new arms run only after every witness cycle declines to nominate. The paid-anchor arm initializes from the original witness grades and uses the original proposal order. It can send a settled winner or a challenger with a proved anchor gain at the cap to independent proof. The Halving arm uses the same cache and shared ceiling of eight new validation lookups. Both arms use the same single paired admission from the Promptolution protocol. A prior witness nomination, including one whose proof rejected it, keeps its original result and charges.

The gate requires a positive paired 95% lower endpoint against both matched-cap Halving and the strongest affordable recorded control on each task and pooled. The matched-cap comparison also requires total lookup cost at or below Halving's. The strongest affordable comparison includes the published fixed GEPA and Halving settings, original witness and fallback arms, and retention. The replay verifies earlier scored control traces and the published matched-cap Halving totals.

## Results

| Scope | Original witness passes / lookups | Anchors passes / lookups | Matched-cap Halving passes / lookups | Strongest affordable GEPA passes / lookups |
| --- | ---: | ---: | ---: | ---: |
| GSM8K | 2,473 / 711 | 2,473 / 731 | 2,473 / 719 | 2,310 / 698 |
| SST‑5 | 1,348 / 729 | 1,432 / 831 | 1,469 / 852 | 1,236 / 815 |
| Pooled | 3,821 / 1,440 | 3,905 / 1,562 | 3,942 / 1,571 | 3,546 / 1,513 |

Fallback was eligible in eight of 64 episodes. On GSM8K, the anchor race saved four validation lookups against matched-cap Halving and bought a 16-lookup proof that rejected the challenger. Both methods retained the same held-out score. On SST‑5, the anchor race left the winning identity unsettled at the cap in four of seven episodes and sent one of those challengers to proof. Across SST‑5, it promoted four challengers, while matched-cap Halving promoted six. The anchor arm lost 37 passes and saved 21 lookups. Its paired 95% interval against matched-cap Halving was −2.083 to −0.521 percentage points on SST‑5 and −1.059 to −0.260 pooled.

The anchor arm beat the strongest affordable GEPA point by 163 GSM8K passes and 196 SST‑5 passes, with positive paired lower endpoints on both tasks. The matched-cap Halving comparison blocked transfer. This comparison measures selection among recorded programs with fixed predictions. Fresh prompt generation and live performance remain unverified. [Full receipt, control choices, and case-paired intervals](promptolution-paid-anchor-transfer-results-v1.json)

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. The collector verified every pinned public CSV blob and produced the expected archive hash. With sockets and DNS blocked, 112 targeted tests passed and two complete replays matched byte for byte. The runner rejected the previous seal and the prospective live-plan preview reproduced byte for byte. Storage Guard measured 6.1 GiB free. The 39 MiB export and archive overlay and the bounded publication worktree used the standing 0.2 GiB LAB exception. The replay made zero provider requests. [Scope, proof, and charge tests](../tests/unit/test_promptolution_paid_anchor_transfer.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.promptolution_witness_capture --out PREDICTIONS.json
python -B -m benchmarks.promptolution_paid_anchor_transfer \
  --corpus PREDICTIONS.json \
  --execute 094d7a0ea1add0846c108136711042fe3f247c4166f9ff8bc6be39ab3f7cce0b \
  --out NEW_REPORT.json
```
