# Match realized lookup costs on the later MMLU model splits

At cap 52, sequential GEPA spent 83,250 lookups. The CPO route that widens on a third incumbent pass spent 50,951. To measure how much of the holdout gap persists at comparable cost, this replay sweeps official sequential and batched GEPA 0.1.4 at every integer paid search cap from 20 to 68 on the same 16 panels. It also reruns 12 published CPO settings. Both methods use the original 32 four-cycle episodes, starting prompts, proposal blocks, search rows, recency archive, and independent qualification. [Frozen model split](routed-finalist-model-transfer.md) · [CPO routing experiments](routed-witness-split.md)

Costs count distinct episode-local search lookups and the qualification replies through each decision. At each CPO cost, the fixed comparison takes the highest-scoring affordable GEPA setting from the entire sweep. The task-specific comparison chooses a setting separately for each subject, shared by both of its model panels. It can also retain that subject's starting prompts at zero additional lookup cost. Both comparisons select using measured holdout scores and are retrospective. [Paid budget allocator](../benchmarks/paid_budget_frontier.py) · [Replay runner](../benchmarks/routed_model_cost_frontier.py)

For four CPO settings, 4,096 paired draws resample cases within each subject. Each sampled case carries both models and all 32 episode outcomes. The best affordable fixed GEPA setting is selected again on each draw under the original realized costs. The central 95% ranges measure sensitivity to the composition of these archived cases. [Paired resampling](../benchmarks/independent_mmlu_cost_uncertainty.py)

## Results

Each cell reports holdout passes / paid lookups across all 16 panels. The fixed GEPA settings shown are sequential.

| CPO policy | CPO | Best affordable fixed GEPA | Task-specific GEPA with hindsight |
| --- | ---: | ---: | ---: |
| Seeded | 12,165 / 46,040 | Cap 32 · 12,189 / 45,513 | 12,281 / 45,328 |
| Widen on third pass | 12,201 / 50,951 | Cap 35 · 12,202 / 50,399 | 12,286 / 50,358 |
| Widen on third miss | 12,219 / 52,605 | Cap 35 · 12,202 / 50,399 | 12,286 / 50,358 |
| Routed backup | 12,223 / 54,166 | Cap 36 · 12,209 / 54,160 | 12,287 / 53,317 |
| Always-wide backup | 12,251 / 69,527 | Cap 42 · 12,237 / 65,808 | 12,298 / 69,256 |
| Always wide with bounds | 12,253 / 73,015 | Cap 45 · 12,240 / 71,860 | 12,299 / 70,792 |

Widening on a third pass trailed cap-52 sequential GEPA by 52 passes. At comparable realized cost it trailed cap-35 sequential GEPA by **one pass and spent 552 more lookups**. Widening on a third miss led the affordable fixed point by 17 passes and tied the score of sequential GEPA at cap 39 with **6,110 fewer lookups**. The paired ranges against the reselected affordable control were −66 to +61 for the third-pass rule and −49 to +78 for the third-miss rule. All four audited ranges include zero. Five of the 12 CPO settings outscored the best affordable fixed GEPA setting at observed totals. The task-specific hindsight allocation scored higher within all 12 CPO budgets. [Complete cost points and paired comparisons](routed-model-cost-frontier-results-v1.json)

## Where CPO lost holdout passes

The third-pass route lost 81 of the 512 paired episodes against sequential GEPA at cap 35, with a gross deficit of 167 passes before offsetting wins. GEPA kept the starting prompt in 46 of those episodes, accounting for 90 gross lost passes. In nine episodes, its winning prompt was offered to CPO and had a strict gain on both the validation and qualification cases for that cycle, but CPO did not nominate it. Those episodes accounted for 19 gross lost passes. Against cap 52, holding the starting prompt accounted for 75 of 219 gross lost passes. These labels inspect the archived outcomes after selection. They point to preserving strong starts as a separate problem from finding more candidates. Earlier fixed increases in the gain required to leave the start had mixed results on other cohorts. [Loss attribution and remaining causes](routed-model-cost-frontier-results-v1.json) · [Earlier starting-prompt margin study](starting-prompt-margin.md)

The follow-up tests separate qualification groups before leaving the start and measures the value of reserving its archive comparison for the final cycle. [Starting-prompt protection](routed-start-protection.md)

## Reproduce

Use the hash-pinned GEPA 0.1.4 dependency. Preview the sealed plan, then replay to a fresh output path.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.routed_model_cost_frontier
PYTHONHASHSEED=0 python -B -m benchmarks.routed_model_cost_frontier \
  --execute 97cda68cb455500dffc3553b0e647c2b6a32c8f4e035cd30267b7681c24ac244 \
  --out NEW_REPORT.json
```

Two source-export replays matched byte for byte with sockets and DNS blocked. They reproduced 64 published GEPA trace hashes and 192 CPO trace hashes, along with the associated scores and lookup costs. Five existing frontier and resampling tests passed. The CLI rejected an incorrect seal and preserved an existing report when given its output path. Storage Guard measured 14.1 GiB free. The 13.4 MB scratch overlay was removed under the standing LAB exception. Fresh prompt generation and provider spending remain unverified.
