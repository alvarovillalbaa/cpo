# Recover a stalled repair search

The [feature stress test](opening-probe-robustness.md) found two ways for routed repair to stop too early. An opening that improves field scores can tie the incumbent on exact passes. A paid training batch can also pass every probe while the opening still misses validation cases. Both failures prevented the cycle from spending a funded repair stage.

Set `recover_stalls=True` in `run_routed_repair_cycle` to let a tied opening supply repair context when `field_credit=True`. The opening must keep every validation row’s exact outcome and matched-field count and improve the field count on at least one row. If all probes in the first batch pass, the cycle may spend its remaining stage on unused training rows. The overall search cap and two-stage limit still apply. A later proposal needs strict exact validation gain to become the nominee, and the final nominee still faces independent qualification. [API](../cpo/routed_repair_cycle.py)

## Results

The benchmark reproduced the prior routed and GEPA totals on the 60 development panels and added 60 disjoint transfer panels. The table gives holdout passes out of 1,080 and total counted calls on the transfer panels.

| Method | Clean passes / calls | Missing field passes / calls | Redundant metadata passes / calls |
| --- | ---: | ---: | ---: |
| Routed repair | 1,080 / 3,928 | 1,035 / 3,845 | 1,074 / 3,915 |
| Routed repair with stall recovery | 1,080 / 3,928 | 1,065 / 3,920 | 1,080 / 3,930 |
| Sequential GEPA | 1,011 / 4,109 | 1,011 / 4,109 | 1,011 / 4,109 |
| Batched GEPA | 830 / 4,288 | 830 / 4,288 | 830 / 4,288 |

Stall recovery preserved every baseline holdout pass across both cohorts and all feature modes. It recovered 18 clean development passes, including the panel whose opening tied on exact validation. On transfer it matched the clean router and recovered six passes with redundant metadata and 30 with one field missing.

The clean and redundant-feature transfer modes cleared both GEPA gates. With a field missing, stall recovery beat sequential GEPA by 54 passes and used 189 fewer calls, while losing 15 matched critical passes across three panels. At least one panel also fell below the 14-pass floor for the batched GEPA comparison. The full transfer gate failed. The option stays opt-in. Live qualification remains pending. [Sealed results](opening-stall-recovery-results-v1.json)

The follow-up reserved additional training probes only for a passing batch that would end search. It recovered the missing-field critical passes and cleared both GEPA gates on fresh scripted panels across four feature modes. [Funded fallback probes](opening-probe-fallback.md)

## Reproduce offline

Use GEPA 0.1.4, the source at commit `2c460eb0469a1e112e1cf88b3c11206480e074cf`, and a fresh output path to reproduce the original seal.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.opening_stall_recovery
PYTHONHASHSEED=0 python -B -m benchmarks.opening_stall_recovery \
  --execute baf8c451a7a043c3610bdab362e37a803d3938a40f421fa84661de60bb7b49e9 \
  --out NEW_REPORT.json
```

Two source replays and an installed-wheel replay blocked sockets and DNS and matched byte for byte. Each covered 120 scripted panels under three feature modes and 240 native GEPA paths. The updated wheel also reproduced the prior 90 panel traces with stall recovery disabled. Fourteen focused tests passed in each environment. The runner rejected a changed seal and preserved an existing report. Storage Guard measured 4.6 GiB free and both scratch exports were removed under the standing LAB exception. [Verification receipt](opening-stall-recovery-verification-v1.json)
