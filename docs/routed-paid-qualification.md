# Skip fresh search after paid qualification rules out a gain

In the four-cycle MMLU replay, an archive comparison can read the incumbent's entire qualification panel before fresh search. If every observed incumbent reply passes, no challenger can strictly improve on that same panel. This study checks whether reusing those replies can avoid fresh validation work without paying for a separate precheck. [Starting-prompt comparison](routed-start-model-confirmation.md) · [Independent precheck](qualification-precheck.md)

## Protocol

Every arm uses its original four-cycle trajectory machinery, archive policy, fixed candidate schedule, 52-lookup search ceiling, and qualification cases. The precheck observes only replies returned by the original archive comparison. It can skip search only after a rejected archive challenger and a paid pass from the incumbent on every qualification case. Cases with any failed or unread incumbent reply follow the original search.

- **Ordinary** runs the original schedule.
- **Terminal** skips fresh search when the paid proof holds in the last cycle. The replay requires the exact same deployed prompt at every cycle.
- **All cycles** skips fresh search whenever the proof holds. Earlier skipping can change later archive nominations because a challenger that fails qualification can otherwise enter the archive.

Both official GEPA modes use the same skip policies. Each policy is compared against both GEPA arms with that policy. The joint range resamples the 421 original held-out cases within subjects. It keeps all 512 model and seed trajectories paired. [Replay runner](../benchmarks/routed_paid_qualification.py)

## Results

Each cell reports holdout passes / paid lookups over 512 four-cycle episodes.

| Policy | CPO | Batched GEPA, cap 52 | Sequential GEPA, cap 52 |
| --- | ---: | ---: | ---: |
| Ordinary | 17,724 / 49,330 | 17,694 / 57,271 | 17,721 / 81,537 |
| Terminal | 17,724 / 49,051 | 17,694 / 57,120 | 17,721 / 81,372 |
| All cycles | 17,724 / 48,868 | 17,694 / 56,967 | 17,718 / 80,889 |

The terminal policy skipped 15 CPO searches and saved 279 lookups. It saved 151 lookups for batched GEPA and 165 for sequential GEPA. Every cycle deployed the same prompt as its ordinary control. CPO saved 14.1% and 39.7% of lookups against the respective matched controls. The joint quality range stayed −55 to +58 passes, leaving the gate inconclusive.

Skipping in all cycles saved 462 CPO lookups across 24 skipped searches, including nine before the final cycle. CPO and batched GEPA preserved their final prompts in this replay. Sequential GEPA changed one final prompt and lost three held-out passes. Its outcome shows that skipping search when a current promotion is impossible can still affect later choices. The terminal rule gives a decision-preserving saving on this cohort. These data come from recorded outcomes and fixed prompt rosters. Fresh-model performance remains unverified. [Full results and traces](routed-paid-qualification-results-v1.json)

## Reproduce

Use GEPA 0.1.4 and the bundled archives.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.routed_paid_qualification
PYTHONHASHSEED=0 python -B -m benchmarks.routed_paid_qualification \
  --execute f839ac08dc15d4466f6497cda44f60ea11250cc9561e413d5c166c485d26d0b9 \
  --out NEW_REPORT.json
```

Two source-export runs matched byte for byte with sockets and DNS blocked. They reproduced 48 published control traces and checked 6,144 cycle deployments for the terminal rule. Ten focused tests passed, including rejection of incomplete evidence and per-cycle state reset. The CLI rejected a wrong seal and an existing output path. Storage Guard measured 20.9 GiB free. The 15.8 MB temporary overlay was removed under the standing LAB exception. [Focused tests](../tests/unit/test_routed_paid_qualification.py)
