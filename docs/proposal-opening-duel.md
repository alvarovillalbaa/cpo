# Choose which proposal to validate first

Finishing late challengers increased promotions and reduced holdout passes. This replay tests an earlier choice using the existing proposal-driven PromptEval experiment. CPO can buy validation replies from its two opening proposals to decide which one gets scored first. The original independent qualification still compares only the final nominee with the incumbent. [Previous experiment](proposal-terminal-completion.md) · [Parent replay](expected-cost-proposal-replay-results-v1.json)

**Miss-only** scores both proposals on the first validation case the incumbent fails. **Paired** also scores both proposals on the first case the incumbent passes when one exists. It weights each reply by the size of its incumbent outcome group and switches the opening order only when the repair scores higher. **Matched probes** buys the same replies as Paired and retains the original rewrite-first order. **Reverse** always scores the repair first and buys no extra probes. A perfect incumbent skips the probes.

All four policies use the same 72-lookup search ceiling per cycle. The runner deducts the full probe allowance from the engine’s search limit and reuses any probe reply the engine later requests. Paid lookups below include physical search lookups and independent qualification. The replay uses the original proposal blocks, cases, seeds, and qualification rule. Both GEPA controls retain their published search budgets. [Runner](../benchmarks/proposal_opening_duel.py)

## Results

| Policy | Development passes / lookups | Transfer passes / lookups |
| --- | ---: | ---: |
| Original cap-72 CPO | 4,159 / 33,177 | 10,237 / 66,831 |
| Miss-only | 4,161 / 32,629 | 10,235 / 65,665 |
| Paired | 4,163 / 32,395 | 10,234 / 65,281 |
| Matched probes | 4,159 / 32,241 | 10,232 / 65,048 |
| Reverse | 4,163 / 33,196 | 10,215 / 67,036 |
| Sequential GEPA | 4,139 / 44,944 | 10,236 / 91,649 |
| Batched GEPA | 4,176 / 44,194 | 10,263 / 88,226 |

On eight retrospective transfer panels, Paired changed the opening order in 94 of 1,024 cycles and reused 3,040 of its 4,096 probe replies. It saved 1,550 lookups and scored three fewer passes than original cap-72 CPO. Against Matched probes, it gained two passes and used 233 more lookups. Miss-only gained one pass over Paired and used 384 more lookups. The original search remains the default.

Paired scored 29 fewer passes than batched GEPA and used 22,945 fewer lookups. The joint paired 95% range against both GEPA controls was −79 to +17 passes. The range resamples held-out cases within subjects, preserving the paired model and seed results for each sampled case. It describes this archive and leaves accuracy superiority unresolved. [Panel traces, counters, and paired ranges](proposal-opening-duel-results-v1.json)

The follow-up traced the original cap-72 and batched GEPA deployments to find when their holdout gap accumulated. [Deployment path audit](proposal-gap-audit.md)

## Reproduce offline

Use pinned GEPA 0.1.4 and a fresh output path.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.proposal_opening_duel
PYTHONHASHSEED=0 python -B -m benchmarks.proposal_opening_duel \
  --execute b9f79ac6d797a6740c705f51f8a178617d545994e2bf4eebe91565b153d7f212 \
  --out NEW_REPORT.json
```

Two clean source replays blocked sockets and DNS and matched byte for byte. Each replay exercised 6,144 experimental cycle paths and reproduced all 48 published panel-control traces. Nine focused tests passed. The runner rejected a stale seal and preserved an existing report. Storage Guard measured 10.2 GiB free. The 26.4 MB scratch export was removed under the standing LAB exception. [Tests](../tests/unit/test_proposal_opening_duel.py) · [Verification receipt](proposal-opening-duel-verification-v1.json) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
