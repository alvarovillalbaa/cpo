# Choose a certificate screen from the paid incumbent score

The route reads the incumbent’s validation panel once. It uses immediate certification if the remaining validation budget can fund two best-case proofs. Each proof needs at least one more paid pass than the incumbent has. Otherwise the route uses the reserved probe batch. With six validation cases and cap 13, the rule uses immediate certification when the incumbent passes at most two cases. The decision uses paid validation replies and never reads qualification outcomes. The selected screen reuses the incumbent replies and receives the original cap. [Replay runner](../benchmarks/recorded_certificate_budget_route.py) · [Immediate certificate cycle](sequential-certificate-cycle.md)

The replay compares the two fixed screens and the route, each at one and two qualification gains. It reproduces the original 102 panels and transfers the frozen settings to 32 archived Flan-T5-XL and Minotaur-15B panels. Those two checkpoints were absent from the original BBH and LMentry studies. The transfer covers eight previously studied BBH tasks and six previously studied LMentry tasks, plus BBH causal judgment and LMentry ends-with-word. The two additional tasks also have two panels each. [Archive provenance](recorded-shortlist-model-transfer.md)

## The budget rule missed the gate

The route needed to use at most the cheaper fixed screen’s lookup count and retain a nonnegative paired 95% lower endpoint against both fixed screens at the same qualification margin. It passed zero of 16 cohort-and-margin checks. On original BBH trials where the rule chose immediate certification at one gain, that choice lost 44 passes. The same routing decision on previously studied BBH tasks with the other checkpoints added 130 passes. On disjoint MMLU, the route fell 20 passes behind the immediate screen because it used the reserved screen on trials that accounted for 20 of the immediate screen’s 22 added passes. The policy selected by the budget rule reproduced the corresponding fixed screen’s exact paid path on every routed trial. [Costs, paired ranges, and path hashes](recorded-certificate-budget-route-results-v1.json)

## Fixed-screen transfer

At one gain, immediate certification improved on the reserved screen in each family’s previously studied task group. It also improved on the new LMentry task at additional cost and lost passes on the new BBH task. The figures below compare the two fixed CPO screens.

| Target tasks | Reserved passes / lookups | Immediate passes / lookups | Pass change and paired 95% range | Lookups saved |
| --- | ---: | ---: | ---: | ---: |
| BBH, eight previously studied tasks | 4,648 / 6,903 | 4,777 / 6,719 | +129 [93, 162] | 184 |
| BBH, causal judgment | 586 / 845 | 575 / 813 | −11 [−18, −5] | 32 |
| LMentry, six previously studied tasks | 4,909 / 5,029 | 5,046 / 4,942 | +137 [95, 179] | 87 |
| LMentry, ends-with-word | 212 / 907 | 262 / 946 | +50 [39, 61] | −39 |

## Compare at the same lookup budget

The transfer replay sweeps both GEPA modes at each integer cap from 6 to 180 under the one-gain, two-gain, and threshold-prechecked two-gain qualification wrappers. It reproduces all published one-gain GEPA cost and score points. Each paired draw reselects the strongest affordable common setting or retained starts. The table shows immediate certification with one qualification gain. The receipt includes all six CPO settings. [Replayed GEPA frontier and attaining subject schedules](recorded-certificate-routing-gepa-transfer-results-v1.json)

| Target tasks | Best affordable fixed control, passes / lookups | Immediate CPO lead and paired 95% range | GEPA subject-tuned hindsight, passes / lookups |
| --- | ---: | ---: | ---: |
| BBH, previously studied tasks | Sequential cap 16, one gain, 4,585 / 5,995 | +192 [154, 226] | 4,887 / 6,471 |
| BBH, causal judgment | Retain starts, 568 / 0 | +7 [−1, 17] | 568 / 0 |
| LMentry, previously studied tasks | Sequential cap 16, one gain, 4,638 / 4,619 | +408 [358, 458] | 4,964 / 4,822 |
| LMentry, ends-with-word | Retain starts, 161 / 0 | +101 [87, 115] | 161 / 0 |

Immediate CPO scored 82 passes above the exact subject-tuned GEPA ceiling under its 4,942-lookup budget on the six LMentry tasks. GEPA’s subject-tuned ceiling stayed 110 passes ahead on the eight BBH tasks. Against reserved CPO on those previously studied tasks, Minotaur accounted for all 129 added BBH passes and 161 added LMentry passes. Flan tied on BBH and lost 24 LMentry passes. On the new LMentry task, Flan accounted for all 50 added passes. Each new-task group contains one task, and its paired range describes the archived cases on that task. Fresh prompt generation and live performance remain unverified.

## Reproduce the route study

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.recorded_certificate_budget_route
PYTHONHASHSEED=0 python -B -m benchmarks.recorded_certificate_budget_route \
  --execute 6973dc2bf5677c890b0ff35bc1ec5ce493f6d546cc4179be5dbe2e709f07d92f \
  --out NEW_ROUTE_REPORT.json
```

The two clean-source runs matched byte for byte at SHA-256 `7c3990f0d153fe1c8cf451bc642a9447ad9c1d2d05bbeb5be0c3e046ea453878`. The runner checked 25,728 paths from both fixed screens and the route, with DNS and outbound sockets blocked. The CLI rejected the predecessor seal. [Route threshold and callback tests](../tests/unit/test_recorded_certificate_budget_route.py)

## Reproduce the matched transfer study

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. [Wheel requirement](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.recorded_certificate_routing_gepa_transfer
PYTHONHASHSEED=0 python -B -m benchmarks.recorded_certificate_routing_gepa_transfer \
  --execute 529176f285b6a5080ab291057b37b69f2796c500fb54530d1713ed9c9f699c6d \
  --out NEW_TRANSFER_REPORT.json
```

Two clean-source runs with DNS and outbound sockets blocked matched byte for byte at SHA-256 `3f21b7d5ca9725ca36501b12f4b49a68d003fd611893ef121d6ebf0738cdfb98`. They checked 33,758 legacy and 14,947 threshold-prechecked GEPA paths. Another 2,560 direct schedule-setting executions verified the selected fixed controls and subject schedules. All 27 targeted tests and four subtests passed. The CLI rejected the route seal before writing a transfer report. Storage Guard measured 2.9 GiB free. The bounded export, GEPA wheel overlay and publication worktree fit the standing 0.2 GiB LAB exception. No provider requests were sent. [Transfer runner](../benchmarks/recorded_certificate_routing_gepa_transfer.py)
