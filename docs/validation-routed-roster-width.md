# Measure how roster width changes CPO routing

The Promptolution replay favored settled CPO over validation routing on two-challenger rosters. This benchmark tests the same contrast on the 2,048 archived BBH, LMentry, and MMLU episodes. It runs each policy on the original eight challengers per cycle and on the first two in that same order. Starting prompts, seeds, validation, independent qualification, and holdout stay fixed. The wide routed paid traces reproduce exactly. The narrow layout also replays the 11 Promptolution native GEPA settings, five halving settings, and retention. [Benchmark](../benchmarks/validation_routed_roster_width.py) · [Promptolution evidence](validation-routed-promptolution.md)

Each cell gives held-out passes and paid lookups. The cohorts reuse some cases, so the totals describe the recorded mix. [Sealed results](validation-routed-roster-width-v1.json)

| Cohort | Two, settled | Two, routed | Eight, settled | Eight, routed |
| --- | ---: | ---: | ---: | ---: |
| Additional MMLU | 7,397 / 7,472 | 7,398 / 7,596 | 7,397 / 6,211 | 7,395 / 5,490 |
| Bounded BBH | 6,309 / 15,123 | 6,310 / 15,310 | 6,338 / 12,340 | 6,338 / 11,451 |
| Bounded LMentry | 5,576 / 14,007 | 5,690 / 17,049 | 6,390 / 15,146 | 6,504 / 12,927 |
| Bounded MMLU | 7,710 / 7,444 | 7,717 / 7,703 | 7,715 / 5,956 | 7,711 / 5,478 |
| Four-case MMLU | 22,358 / 11,709 | 22,355 / 12,008 | 22,366 / 10,522 | 22,365 / 8,798 |
| Tie BBH | 2,147 / 10,941 | 2,167 / 12,475 | 2,138 / 12,520 | 2,122 / 11,117 |
| Tie LMentry | 899 / 5,045 | 929 / 6,676 | 1,004 / 6,863 | 1,013 / 6,053 |
| **Total** | **52,396 / 71,741** | **52,566 / 78,817** | **53,348 / 69,558** | **53,448 / 61,314** |

At two challengers, routed CPO gained 170 passes across the measured mix and used 7,076 more lookups. At eight, it gained 100 passes and saved 8,244 lookups. The direction of the cost difference flipped in all seven cohorts. The narrow route replaced 4,096 training probes with 10,893 additional validation lookups and 279 additional qualification lookups relative to settled CPO. The uniform budget permits six funded cases at two challengers and two at eight. This wider validation depth gives a mechanism for the narrow cost increase. [Uniform round accounting](../cpo/quoted_shared_validation_cycle.py#L12)

The narrow route improved both LMentry cohorts against settled CPO, with paired 95% case ranges of +80 to +150 and +9 to +51 passes. Other narrow paired score ranges included zero. Against the best affordable GEPA or retention choice, it had positive paired lower endpoints on bounded LMentry, tie BBH, and tie LMentry. Against affordable halving or retention, both LMentry ranges were positive and four-case MMLU favored the control by 15 to 51 passes. Each matched comparison reselects the strongest affordable control within each bootstrap draw.

These results identify a narrow-roster cost penalty. They also show that a width-only switch to settled CPO would give up measured LMentry quality. The receipt includes paired differences between widths for each cohort. Fresh-model performance remains open.

## Reproduce offline

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Run the CLI without arguments to preview the seal.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.validation_routed_roster_width \
  --execute bec2caa54f68743f0b7e93556b81cd4791b2e3919629546702697f465db6a9cc \
  --out NEW_REPORT.json
```

Two socket-blocked replays produced byte-identical receipts. All 39 focused tests passed, and the CLI refused a stale seal and an existing output. The replay sent zero provider requests. Storage Guard measured 9.1 GiB free. The isolated source export, GEPA overlay, and publication worktree occupied 122 MiB under the standing 0.2 GiB LAB exception. [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
