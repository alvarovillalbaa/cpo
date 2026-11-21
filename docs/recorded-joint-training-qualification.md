# Combine training and qualification gains after the independent gate

A training check helped the archived AIME trials and hurt ARC-AGI even within the same validation patterns. This replay keeps the same strict validation nominee and requires an exact gain of at least one pass on independent qualification before reconsidering it. It compares two ways to use the reserved training half. [Previous routing study](recorded-calibrated-training-route.md) · [Replay runner](../benchmarks/recorded_joint_training_qualification.py)

- **Training nonloss** keeps the nomination if it ties or improves on the incumbent on the training half.
- **Balanced gain** requires a positive mean of the training and qualification gain rates. It multiplies each signed pass gain by the other panel's width and requires the sum to be positive. Each panel can contribute the same maximum weight.

Balanced gain starts from the exact replies already paid for in independent qualification. It consults new replies only while the weighted gain bounds straddle zero. To order those reads, it uses pass rates and per-prompt prices estimated from paid validation. The order can change cost, and the exact bounds determine the result. The original caps apply to both roles, and held-out replies are scored after deployment. [Sealed scores, costs, and matched comparisons](recorded-joint-training-qualification-results-v1.json)

| Archive and roster | Skip training | Strict training gain | Training nonloss | Balanced gain |
| --- | ---: | ---: | ---: | ---: |
| AIME, original, four challengers | 486 / 1,040 | 489 / 1,117 | 486 / 1,114 | 487 / 1,108 |
| AIME, original, eight challengers | 476 / 1,438 | 485 / 1,530 | 482 / 1,529 | 479 / 1,524 |
| AIME, rotated, four challengers | 4,036 / 7,643 | 4,069 / 8,117 | 4,060 / 8,105 | 4,039 / 8,093 |
| AIME, rotated, eight challengers | 4,002 / 10,908 | 4,062 / 11,487 | 4,042 / 11,477 | 4,003 / 11,461 |
| ARC-AGI, original, four challengers | 1,561 / 1,302 | 1,561 / 1,844 | 1,561 / 1,792 | 1,561 / 1,716 |
| ARC-AGI, original, eight challengers | 1,578 / 1,502 | 1,578 / 2,041 | 1,578 / 1,991 | 1,578 / 1,908 |
| ARC-AGI, rotated, four challengers | 13,878 / 7,007 | 13,757 / 8,226 | 13,858 / 8,123 | 13,876 / 7,940 |
| ARC-AGI, rotated, eight challengers | 13,932 / 8,239 | 13,818 / 9,611 | 13,914 / 9,479 | 13,930 / 9,266 |

On eight-challenger rotated AIME, nonloss gave up 20 of strict training's 60 recovered passes and saved ten lookups. Balanced gain gave up 59 of those passes and saved 26 lookups. Both trailed the best affordable GEPA. Their paired lookup-matched 95% margins were −86 to −14 and −138 to −42, respectively.

On eight-challenger rotated ARC-AGI, balanced gain used 1,027 more lookups and $127.55 more at recorded prices than skipping training. Its only changed deployment lost two held-out passes. Balanced gain still beat the best affordable GEPA by 155 passes, with a paired range of +55 to +258 by lookups and +52 to +257 by historical cost. Skipping the check had already led by 197 and 164 passes at its own lower budgets. The two new rules add evidence from the training panel and fail to produce a better cost-quality result across the two archives.

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Two full socket- and DNS-blocked replays matched byte for byte and reproduced the original GEPA frontiers. An independent check compared all 3,040 deployments and held-out grade vectors with the full-panel formulas. The 45 targeted tests passed from a clean source export, including paid-prefix reuse, unequal panel widths, and the independent gate. The CLI rejected the prior seal. The public selector parity receipt and ordered live-plan preview matched. Storage Guard measured 2.9 GiB free. The export and publication worktree fit the standing 0.2 GiB LAB exception. No provider requests were sent.

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.recorded_joint_training_qualification
python -B -m benchmarks.recorded_joint_training_qualification \
  --execute 1a3aedec06c52ac213c8194efe51cf380caff5937ef518484fdb5777f72d2a1c \
  --out NEW_REPORT.json
```
