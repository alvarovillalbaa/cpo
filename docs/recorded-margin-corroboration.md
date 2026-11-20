# Use stronger qualification to waive a training check

An independent training check recovered passes on the AIME archive. A stronger result on qualification might supply enough evidence by itself and save the training lookups. This replay tests that substitution while keeping both panels disjoint and holding the validation winner fixed. It uses the same ARC-AGI and AIME prompt pools, starting prompts, rosters, case splits, and 180-lookup search cap as the earlier studies. [Training corroboration](recorded-training-corroboration.md) · [Replay runner](../benchmarks/recorded_margin_corroboration.py)

## Protocol

After strict CPO nominates a validation winner, it first proves a gain of at least one on independent qualification. It also preserves every critical incumbent pass and requires nonnegative gain in each family. A contender that passes can meet either of two additional requirements.

- Prove a gain of at least two on the same independent qualification panel.
- Prove a gain of at least one on the first half of the reserved training panel, using five cases on AIME or nine on ARC.

**Strength first** tries the second qualification gain before reading training. **Training first** tries the training check before extending qualification. Both schedules stop as soon as one requirement is met. **Training only** and **strength only** isolate those requirements. The latter uses the same gain-of-two rule while enforcing the same family and critical constraints. Extending qualification reuses every previously read reply. Training lookups count against the search cap.

Every optimizer receives the same incumbent-only qualification precheck. The comparison includes the frozen strict and certified-backup CPO settings, both official GEPA modes, and retaining the start. Holdout cases stay outside every proof. [Matched qualification protocol](recorded-validation-stability.md)

## Results

Each cell reports holdout passes / paid lookups. These are the eight-challenger rotations.

| Policy | AIME | ARC-AGI |
| --- | ---: | ---: |
| Retain start | 4,056 / 0 | 12,944 / 0 |
| Strict CPO | 4,002 / 10,959 | 13,932 / 8,422 |
| Training only | 4,062 / 11,542 | 13,818 / 9,925 |
| Strength only | 4,039 / 11,001 | 13,696 / 8,506 |
| Strength first | 4,042 / 11,477 | 13,864 / 9,239 |
| Training first | 4,042 / 11,569 | 13,864 / 9,948 |
| Certified training backup | 4,073 / 12,534 | 13,822 / 10,589 |
| Batched GEPA | 4,055 / 13,410 | 13,781 / 10,785 |
| Sequential GEPA | 4,074 / 13,720 | 13,785 / 11,962 |

On AIME, the waiver deployed 11 challengers that training alone would have rejected. Together those changes lost 20 held-out passes, with a paired case range of −41 to −1. Strength first avoided 107 training lookups and added 42 qualification lookups, saving 65 overall. It fell 13 passes behind batched GEPA and 32 behind sequential GEPA. The training-only policy scored seven passes ahead of batched GEPA and 12 behind sequential GEPA, with 13.9% and 15.9% fewer lookups. Its joint paired range was −41 to +15. At four challengers, the waiver lost 15 passes compared with training alone. Retaining the original AIME start exceeded every searched arm at either width. [Full results and proof counts](recorded-margin-corroboration-results-v1.json)

On ARC with eight challengers, strength first gained 46 passes and saved 686 lookups compared with training alone. It cleared the matched GEPA gate with a joint range of +25 to +129. Training first produced the same score and missed the batched GEPA savings threshold. Strict CPO achieved 68 more passes on 817 fewer lookups than strength first. The two orders agreed on all 1,520 nomination and deployment decisions across both archives. Strength first used fewer lookups in every measured group.

The AIME result favors keeping the separate training check. A larger gain on the same small qualification panel did not supply equivalent evidence. These are comparisons on reused recorded outcomes and seeded case splits. Fresh-model qualification remains pending.

## Reproduce

Use GEPA 0.1.4 and the bundled archives. Preview the seal, then execute to a fresh report path.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.recorded_margin_corroboration
PYTHONHASHSEED=0 python -B -m benchmarks.recorded_margin_corroboration \
  --execute c591f70c98084aa2e99c00702625164b315459569bf461e61bf4a5e527029f50 \
  --out NEW_REPORT.json
```

Two source-export replays matched byte for byte with sockets and DNS blocked. They reproduced 40 published control traces and verified the training-only deployment against the original training guard in every trial. Eight focused tests passed, including exhaustive checks of the new proof schedules on all 256 four-case binary outcome matrices, with and without training support. The CLI rejected a wrong seal and preserved an existing result. Storage Guard measured 21.5 GiB free. The bounded 15.5 MB overlay was removed under the standing LAB exception. [Focused tests](../tests/unit/test_recorded_margin_corroboration.py)
