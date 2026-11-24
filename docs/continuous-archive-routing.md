# Carry frozen CPO routing decisions across three optimization cycles

The single-cycle experiments held each starting prompt fixed. This replay tests whether the same routing policies help when the deployed prompt becomes the next cycle's incumbent. It uses the three frozen routing tables and fitted static CPO across the same 64 archived model and task pairs. The cohort-budgeted router is primary. [Frozen routing tables and single-cycle results](short-circuit-archive-routing.md) · [Replay runner](../benchmarks/continuous_archive_routing.py)

Each episode reproduces the original start, eight-challenger roster, ten training cases, six validation cases, and four separate qualification cases in its first cycle. Cycles two and three each get eight unused candidates and 20 fresh training, validation, and qualification cases. All 60 search and qualification cases are disjoint within the episode and outside the fixed final holdout. Every policy pays for its actual reads across the three cycles. The final deployment determines the reported holdout score.

The same starts, rosters and role boundaries apply to both GEPA modes. The split-safe menu gives each mode both validation widths and six proof wrappers, over all funded integer caps through 180. An individual GEPA setting uses the same cap, width and proof wrapper throughout the episode. The runner propagates a cap interval only while it has the same incumbent and lookup cost, then directly replays the setting that attains each primary comparison. Before accepting the final trajectories, the runner verifies all first-cycle CPO path hashes and the complete first-cycle native menu. The complete replay covers 2,048 episodes and 6,144 cycle layouts. [Split-safe native comparison](shared-validation-split-safe-transfer.md)

## Three-cycle results

Each cell gives final held-out passes / paid lookups across all three cycles. The native controls spend at most the routed CPO budget for the cohort. The primary gate also requires a positive paired lower endpoint against both fitted static and the best affordable common GEPA setting, a higher score than subject-tuned GEPA, and at most the static CPO cost.

| Cohort | Routed CPO | Static CPO | Best common GEPA | Subject-tuned GEPA | CPO paired 95% range vs subject-tuned | Gate |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| [Bounded BBH](continuous-archive-routing-bounded-bbh-v1.json) | 6,389 / 13,797 | 6,373 / 18,783 | 6,290 / 13,550 | 6,350 / 13,202 | −57 to +129 | Missed |
| [Bounded LMentry](continuous-archive-routing-bounded-lmentry-v1.json) | 6,321 / 15,711 | 6,513 / 19,377 | 5,346 / 14,728 | 5,931 / 15,599 | +310 to +469 | Missed |
| [Bounded MMLU](continuous-archive-routing-bounded-mmlu-v1.json) | 7,725 / 7,696 | 7,722 / 9,307 | 7,711 / 5,683 | 7,717 / 7,234 | −19 to +35 | Missed |
| [Four-case MMLU](continuous-archive-routing-four-case-mmlu-v1.json) | 22,381 / 12,145 | 22,399 / 14,245 | 22,350 / 8,525 | 22,369 / 9,289 | −13 to +37 | Missed |
| [Tie BBH](continuous-archive-routing-tie-bbh-v1.json) | 2,204 / 13,130 | 2,156 / 14,705 | 2,091 / 12,749 | 2,126 / 12,939 | +7 to +153 | Passed |
| [Tie LMentry](continuous-archive-routing-tie-lmentry-v1.json) | 1,028 / 7,195 | 988 / 7,498 | 835 / 7,025 | 919 / 6,508 | +65 to +157 | Passed |
| [Additional MMLU](continuous-archive-routing-additional-mmlu-v1.json) | 7,384 / 7,257 | 7,398 / 9,066 | 7,393 / 0 | 7,399 / 6,001 | −32 to 0 | Missed |

Tie BBH passed after three cycles. Tie LMentry passed at both horizons. The LMentry gain over its subject-tuned GEPA schedule came from homophones (+39 passes) and word-before (+70). That GEPA schedule spent its lookups on homophones and retained the start on word-before. The comparison pools the two task costs. Four-case MMLU passed in one cycle and missed after three, as static CPO finished 18 passes ahead.

The routed policy saved 16,050 lookups and lost 117 passes across all seven cohorts versus static CPO. Bounded LMentry accounted for a 192-pass loss relative to static, even as routed CPO led the budget-matched subject-tuned GEPA schedule by 390 passes. A separate trajectory audit showed the gap to static widening from 68 passes after cycle one to 121 after cycle two and 192 after cycle three. The router made 307 promotions across the three cycles and static CPO made 320. On additional MMLU the router scored below retention and trailed subject-tuned GEPA by 15 passes. Case ranges resample within task, keeping both checkpoints and all seeds together. Native settings that attain the reported points are held fixed during resampling. The experiment measures three-cycle selection among supplied archived prompts. Fresh proposal generation and live model performance remain unverified.

## Reproduce offline

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. [Benchmark requirements](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.continuous_archive_routing --cohort tie-LMentry
PYTHONHASHSEED=0 python -B -m benchmarks.continuous_archive_routing \
  --cohort tie-LMentry \
  --execute 20afdcba73dd02e8c7693a14a31b27c6ec56e5b7b5658363925b31d190b2cb55 \
  --out NEW_REPORT.json
```

Two source replays per cohort matched byte for byte with DNS and outbound sockets blocked. The first-cycle native grid and starting CPO traces reproduced on every panel. A separate audit checked disjoint cases and candidates in all 2,048 episodes and confirmed 192 sampled native settings against direct three-cycle execution. Twenty-six targeted tests passed, including comparison of sparse cap propagation with an independent per-cap replay. Storage Guard measured 10.4 GiB free at preflight. The source export, wheel overlay, and publication checkout fit the standing 0.2 GiB LAB exception. [Targeted tests](../tests/unit/test_continuous_archive_routing.py) · [LAB storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
