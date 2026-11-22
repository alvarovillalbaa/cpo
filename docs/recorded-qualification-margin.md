# Test a qualification gain that survives removing one case

The coverage audit found that several qualified promotions lost held-out passes. This replay keeps the cap-13 complete-panel-reserve screen, its validation nominees, and the original four independent qualification cases. It changes the required qualification gain from one net pass to two. With exact binary grades, a two-pass gain stays positive after any one qualification case is removed. [Coverage audit](recorded-screen-coverage-ceiling.md) · [Replay runner](../benchmarks/recorded_qualification_margin.py)

The incumbent precheck and paid-prefix credit remain in use. Expected-cost scheduling settles the stronger proof as soon as its exact bounds allow. The existing proof allowance still caps spending. The replay uses two mutually disjoint, previously scored archived MMLU cohorts. Each paired draw retains both model panels and all repeated seeds for a sampled case, and reselects the strongest affordable control at the variant’s realized search-plus-qualification cost.

| Archived cohort | Original screen passes / lookups | Two-gain screen passes / lookups | Promotions before → after | Best affordable control and paired margin |
| --- | ---: | ---: | ---: | --- |
| Earlier screen, 896 trials | 26,613 / 10,253 | 26,628 / 10,001 | 36 → 7 | Retain starts, +3, −7 to +9 |
| Disjoint transfer, 960 trials | 56,079 / 9,596 | 56,094 / 9,395 | 19 → 3 | Minimum-proof screen, +24, −4 to +39 |

The stricter proof added 15 held-out passes on each cohort and saved 453 qualification lookups in total. The 29 vetoes on the earlier cohort recovered 34 passes and gave up 19. The 16 on the transfer cohort recovered 37 and gave up 22. On the transfer cohort the two-gain screen led sequential GEPA at cap 16 by 26 passes for 75 more lookups, with a paired 95% range of zero to +45. The range against the strongest affordable control crossed zero on both cohorts. Fresh-model performance remains unverified. [Full results and per-panel traces](recorded-qualification-margin-results-v1.json)

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel.

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.recorded_qualification_margin
python -B -m benchmarks.recorded_qualification_margin \
  --execute bb8be9b799bcd694c26f7645d813116d5f243f97439ecc46a9b7ef243ed4743f \
  --out NEW_REPORT.json
```

Two clean-export replays with DNS and sockets blocked matched byte for byte at SHA-256 `cff0abd264ef74d911c329334c3cd4b9ba5a8dc0f3f8c2c77402c849d7d451ce`. All 41 targeted tests passed. The qualification test enumerated all binary outcomes across four paired cases. A direct audit checked the individual case omissions across all 1,856 archived trials and replayed the selected controls. The CLI rejected the previous seal. Storage Guard measured 3.1 GiB free. The export and publication worktree fit the standing 0.2 GiB LAB exception. No provider requests were sent. [Regression test](../tests/unit/test_recorded_qualification_margin.py)
