# Trade challenger breadth for validation depth under one cap

**Comparison update.** The original GEPA results below use positional cache identities. The corrected replay uses disjoint training and validation cache IDs and gives GEPA both six- and three-case validation options. [Corrected comparison and checkpoint transfer](shared-validation-split-safe-transfer.md)

The previous fallback study left many independently qualifying candidates outside the validation gate. This experiment replaces the strict six-case validation certificate on noncritical panels with successive halving on shared paid cases. It keeps the incumbent qualification precheck, the 19-lookup search cap, the original candidates and case splits, and one exact independent qualification attempt. Panels with critical validation cases use the original strict two-sided search. [Stalled-validation study](qualification-after-stalled-validation.md) · [Replay driver](../benchmarks/budgeted_shared_panel_search.py)

The wide schedule starts with eight challengers and measures up to four on the second case and two on the third. The deep schedule starts with four, then has slots for three, two, two and two challengers on the next four cases. An incumbent reply is charged in every completed round. Each cut ranks candidates by their paid pass count on common cases, using proposal order on ties. A candidate can leave earlier when even all remaining passes could not reach the required score relative to the incumbent. Each schedule tests observed nonloss and observed strict gain as separate nomination rules. With no early elimination they use 17 and 18 search lookups respectively.

```python
from cpo.shared_validation_cycle import run_shared_validation_cycle

result = run_shared_validation_cycle(
    incumbent,
    candidates,
    validation_rows,
    qualification_rows,
    evaluate,
    metric_limit=19,
    qualify=qualify,
    schedule='wide',
    validation_gain=0,
    minimum_gain=1,
)
```

The cycle is opt-in. The validation margin applies to the common cases actually read. The separate qualification proof controls deployment. [Package API](../cpo/shared_validation_cycle.py)

The original BBH and LMentry cohorts and both archived MMLU cohorts contribute 102 model panels, 32 schedules and two qualification margins. The replay reprices all 2,100 native GEPA settings for each cohort. Each subject can choose a setting using held-out hindsight, with one setting shared by both checkpoints and all schedules and a joint cost limit equal to CPO's paid search and qualification. Paired ranges against strict CPO resample held-out cases within subject and keep both checkpoints and all schedules together for each case. [Published native comparison](paired-order-gepa-comparison.md)

## Results

The table gives held-out passes and paid lookups at one independent qualification gain. GEPA is priced at the wide nonloss schedule's realized budget. [BBH](budgeted-shared-panel-bbh-results-v1.json) · [LMentry](budgeted-shared-panel-lmentry-results-v1.json) · [Earlier MMLU](budgeted-shared-panel-earlier-mmlu-results-v1.json) · [Disjoint MMLU](budgeted-shared-panel-disjoint-mmlu-results-v1.json)

| Cohort | Strict two-sided CPO | Wide with observed gain | Wide with observed nonloss | GEPA at the wide nonloss budget |
| --- | ---: | ---: | ---: | ---: |
| BBH | 9,548 / 15,059 | 9,704 / 18,064 | 9,840 / 20,209 | 9,796 / 20,136 |
| LMentry | 5,650 / 8,276 | 5,941 / 10,578 | 6,078 / 11,379 | 5,627 / 11,343 |
| Earlier MMLU | 26,619 / 13,363 | 26,653 / 15,162 | 26,642 / 17,421 | 26,654 / 10,802 |
| Disjoint MMLU | 56,094 / 12,701 | 56,095 / 14,758 | 56,034 / 17,005 | 56,116 / 11,534 |

The wide nonloss policy gained 292 BBH and 428 LMentry passes over strict CPO, with paired 95% ranges of +228 to +356 and +363 to +498 passes. Its point scores exceeded the corresponding native ceilings by 44 and 451 passes. The conditional paired ranges against the specific GEPA schedules attaining those ceilings were −38 to +124 on BBH and +349 to +552 on LMentry. The comparisons fix the selected GEPA schedules across draws. The two deeper shared-panel controls scored below wide nonloss on both cohorts.

On earlier MMLU the wide observed-gain policy finished one pass behind the affordable GEPA ceiling, using 4,360 more lookups than its attaining schedule. On disjoint MMLU the wide nonloss policy lost 82 passes to its matched GEPA schedule, with a conditional paired range of −153 to −12. At two qualification gains, the native menu led all four CPO variants on all four cohorts. Fresh-model performance remains unverified.

## Reproduce offline

Use Python 3.12, the pinned GEPA 0.1.4 benchmark dependency and a fresh output path. [Benchmark requirements](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.budgeted_shared_panel_search \
  --cohort BBH --execute e076b87f296ca1f6746f5e989a4d9400c7a731a1f204763ede0baaea22261929 --out NEW_BBH.json
PYTHONHASHSEED=0 python -B -m benchmarks.budgeted_shared_panel_search \
  --cohort LMentry --execute 452715bcba9b11ef089748e584eb63102c702bdc5db2741ad02ea166488531e9 --out NEW_LMENTRY.json
PYTHONHASHSEED=0 python -B -m benchmarks.budgeted_shared_panel_search \
  --cohort earlier-screen-cohort --execute a1a575c1f2bee6cbaad6176ef2c2bdddd1fbcbd3503ea7c78f0c0e419ca31adf \
  --out NEW_EARLIER_MMLU.json
PYTHONHASHSEED=0 python -B -m benchmarks.budgeted_shared_panel_search \
  --cohort disjoint-transfer-cohort --execute f492164461083793ec8083f9a53b6cafa91662158319bc78a9d48a021ee61315 \
  --out NEW_DISJOINT_MMLU.json
```

The clean-source and separately installed CPO wheel reports matched byte for byte on all four cohorts. The package API reproduced the prototype's original paid paths. The new replay also independently reran the one-gain wide nonloss GEPA comparators and checked their scores and costs per subject. Fourteen source tests and five installed-wheel tests passed. Storage Guard measured 1.9 GiB free. The temporary source, wheel and publication checkout fit the standing 0.2 GiB LAB exception. DNS and outbound sockets were blocked. [Targeted tests](../tests/unit/test_budgeted_shared_panel_search.py) · [LAB storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
