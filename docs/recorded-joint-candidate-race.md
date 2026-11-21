# Race training and validation before the single qualification attempt

The adaptive validation race improved ARC-AGI and weakened AIME. It chose one challenger before seeing whether that prompt could beat the incumbent on training. This replay instead searches for the first challenger with strict gains on both panels. It keeps the original rosters, case roles, search cap, and single independent qualification attempt. It first measures incumbent validation. If there is room to improve, it measures the incumbent on the reserved training half. Both reads count as search. [Adaptive validation race](recorded-adaptive-certificate-race.md) · [Replay runner](../benchmarks/recorded_joint_candidate_race.py)

The two new schedules rank challengers by estimated reads divided by the probability of settling both certificates in their favor. The estimate reuses the earlier quarter-bin model based on paid replies. One schedule reads a challenger's training cases only after its validation gain is certified. The other can read either panel and orders it by estimated reads per chance of rejection. Both check the full remaining reserve before buying another reply and settle each gate with exact bounds. A challenger with a protected validation loss cannot qualify.

| Archive and roster | Adaptive validation passes / lookups | Joint race, validation first | Joint race, adaptive order |
| --- | ---: | ---: | ---: |
| AIME, original, four challengers | 486 / 951 | 486 / 1,287 | 491 / 1,091 |
| AIME, original, eight challengers | 482 / 1,120 | 479 / 1,778 | 483 / 1,467 |
| AIME, rotated, four challengers | 4,070 / 6,821 | 4,074 / 9,510 | 4,070 / 8,204 |
| AIME, rotated, eight challengers | 4,073 / 8,528 | 4,066 / 13,455 | 4,065 / 10,920 |
| ARC-AGI, original, four challengers | 1,539 / 1,430 | 1,543 / 1,465 | 1,542 / 1,450 |
| ARC-AGI, original, eight challengers | 1,539 / 1,470 | 1,543 / 1,505 | 1,542 / 1,478 |
| ARC-AGI, rotated, four challengers | 13,750 / 7,708 | 13,837 / 9,528 | 13,835 / 8,594 |
| ARC-AGI, rotated, eight challengers | 13,817 / 8,699 | 13,932 / 11,735 | 13,924 / 10,139 |

On eight-challenger rotated ARC-AGI, the adaptive joint race changed 28 deployments, gained 107 held-out passes and spent 1,440 more lookups than the adaptive validation race. It saved 1,596 lookups and lost eight passes against the validation-first joint race. It led the best affordable GEPA setting by 140 passes with paired 95% case ranges of +81 to +199 by lookups and +79 to +197 by historical cost. The earlier ARC-AGI policy that only checked independent qualification still scored 13,932 on 8,239 lookups. [Matched budgets and full results](recorded-joint-candidate-race-results-v1.json) · [Earlier qualification result](recorded-calibrated-training-route.md#frozen-rule-on-the-math-archives)

On eight-challenger rotated AIME, adaptive ordering saved 2,535 lookups and lost one pass against validation-first. It still used 2,392 more lookups and scored eight fewer passes than the earlier adaptive validation race. Its paired lookup-matched margin against GEPA was −59 to +7. Reordering the two proofs lowered the cost of joint nomination, but the joint race did not improve the cost-quality tradeoff on both archives.

A hindsight audit priced exact certificates for the full roster. It measured which losses came from the gate requirements and how much headroom remained for better selection. [Fixed-roster ceilings](recorded-math-roster-ceiling.md)

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Two socket- and DNS-blocked replays matched byte for byte and reproduced the original GEPA frontiers. An independent audit checked all 3,040 nominations and deployments against complete panel grades. All 51 targeted tests passed, including 512 exhaustive small boards on each schedule, and the CLI rejected the prior seal. The public selector parity receipt and both live plan previews reproduced. Storage Guard measured 2.9 GiB free. The source, wheel, and publication worktree fit the standing 0.2 GiB LAB exception. No provider requests were sent.

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.recorded_joint_candidate_race
python -B -m benchmarks.recorded_joint_candidate_race \
  --execute 261b86df71989b5c7ced36b65c186a5b07aa016ef74cee6053820ab69d4294ee \
  --out NEW_REPORT.json
```
