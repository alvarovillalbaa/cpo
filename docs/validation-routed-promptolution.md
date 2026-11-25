# Test validation-routed CPO on two-challenger rosters

The routed opening was previously tested on wider archived rosters. This transfer uses the packaged policy with its original rules on the saved Promptolution GSM8K and SST-5 predictions. Each task has 32 three-cycle episodes with two challengers per cycle. The replay preserves the original starting prompts, layouts, six-case validation panels, four-case independent admission panels, and 90 held-out cases per task. It replays the adaptive and settled CPO baselines and every native GEPA, witness, halving, and retention control against their published paid traces. [Original Promptolution protocol](promptolution-settled-episode-transfer.md) · [Routed policy](validation-routed-episode.md) · [Benchmark](../benchmarks/validation_routed_promptolution.py)

Each cell shows held-out passes and charged lookups. The native comparison uses the best setting affordable at the routed arm's realized lookup cost. Its paired range resamples physical cases within each task and reselects the strongest eligible setting on each draw. [Sealed results](validation-routed-promptolution-v1.json)

| Scope | Adaptive CPO | Settled CPO | Fixed uniform | Validation-routed CPO | Affordable native GEPA |
| --- | ---: | ---: | ---: | ---: | ---: |
| GSM8K | 2,451 / 883 | 2,472 / 906 | 2,540 / 1,177 | 2,440 / 850 | 2,270 / 820 |
| SST-5 | 1,434 / 1,465 | 1,452 / 1,549 | 1,439 / 1,638 | 1,439 / 1,598 | 1,295 / 1,256 |
| **Pooled** | **3,885 / 2,348** | **3,924 / 2,455** | **3,979 / 2,815** | **3,879 / 2,448** | **3,565 / 2,148** |

Routed CPO gained 314 pooled passes over affordable GEPA and used 300 more lookups. The paired 95% range was +3.77 to +7.12 percentage points. Against pooled successive halving it gained 59 passes with 437 additional lookups. The SST-5 paired range against halving included zero.

Against settled CPO, routing saved seven lookups and lost 45 pooled passes. The paired 95% range was −1.30 to −0.28 percentage points. Against adaptive CPO, it used 100 more lookups, lost six passes, and had a paired range spanning zero. Routing chose narrow halving in 16 GSM8K episodes and one SST-5 episode. Keeping it opt-in preserves a higher-scoring settled choice on this narrow archive. The replay measures allocation over recorded programs. Fresh-model performance remains open.

## Reproduce offline

Use Python 3.12 with the hash-pinned GEPA 0.1.4 wheel and the reduced Promptolution corpus at SHA-256 `729bba5141874b28e3b172757d5e009f6e847f2b04050c75359d6273a01c9491`. The existing collector reconstructs that corpus from the pinned public prediction files. [Collector](../benchmarks/promptolution_witness_capture.py)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.validation_routed_promptolution \
  --corpus PREDICTIONS.json \
  --execute c7fea8c8bb987100c6027c42c460fcc1484c861636c44adf26733bd8fa6ba3eb \
  --out NEW_REPORT.json
```

Two socket-blocked replays produced byte-identical results, and all 38 focused tests passed. The CLI rejected a stale seal and a changed corpus without creating output. The replay sent zero provider requests. Storage Guard measured 9.1 GiB free. The isolated source export, verified corpus copy, GEPA overlay, and publication worktree occupied 122 MiB under the standing 0.2 GiB LAB exception. [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
