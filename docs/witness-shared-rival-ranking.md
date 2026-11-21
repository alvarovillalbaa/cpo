# Measure the backup selection gap on a shared proof panel

Incumbent reply reuse resolved more MMLU proofs and qualified zero backups. This replay asks whether another already-paid candidate could have qualified in those slots and whether paid search grades can identify that candidate. The first proof, eligible retry slots, shared panels, incumbent cache, per-retry reservation, and cohort budgets come from the published reply-reuse comparison. [Reply-reuse results](witness-shared-incumbent-proof.md) · [Runner](../benchmarks/witness_shared_rival_ranking.py)

Each retry chooses one already-graded candidate other than the incumbent and the rejected nominee. The published smoothed pass rate is the control. The paired-margin rule ranks net paired validation wins against the incumbent with shrinkage for sparse support. The case-adjusted rule compares each paid reply to other prompts' smoothed pass rate on that case. Both reuse the earlier first-nominee ranking definitions and keep the published backup on ties. The direct queue is also measured. Admission results and cost from the other benchmark family choose the transferred rule. [Paid ranking definitions](witness-paid-nominee-ranking.md)

The audit also evaluates every eligible backup independently on the same cases at the original retry cap. One hindsight ceiling keeps the published funded slots and the actual lookup cost of each retry. A second ceiling allows selecting or skipping a retry in every originally eligible slot while preserving the funded direct offers, chronological order, and the full reservation required before each proof. Each ceiling may retain the incumbent. The ceilings use held-out grades after pricing the proof and show how much improvement was available within the enumerated scope. The deployable rankings use paid search grades alone to select a rival.

## Results

| Cohort | Eligible retry slots | Paid candidates priced across those slots | Slots with an improving qualified backup | Extra passes at the original funded costs | Extra passes with hindsight across the queue |
| --- | ---: | ---: | ---: | ---: | ---: |
| BBH and LMentry | 66 | 986 | 34 | +64 | +132 |
| MMLU prior subjects | 22 | 182 | 0 | 0 | 0 |
| MMLU additional subjects | 14 | 196 | 1 | +3 | +3 |

On the prior MMLU subjects, no eligible backup completed a promotion certificate within its existing cap. On the additional subjects, two slots had a qualifying backup and one improved held-out accuracy. That backup was already affordable in the original funded slot. Allowing hindsight to pick different funded slots added no further MMLU passes. Together the two MMLU cohorts gave the queue only three additional passes across 378 candidate prices. This bounds the benefit of changing backup selection under the current trigger, panel, and reservation. The earlier larger MMLU headroom used other proof panels and eligibility rules.

Neither paired margin nor case adjustment changed holdout totals or lookup costs in any cohort. Case adjustment changed three funded rivals on BBH and LMentry. The outside-family fit selected direct-only for BBH and LMentry and retained the published reply-reuse policy for both MMLU cohorts. The paired lower endpoint against the single proof remained positive only on BBH and LMentry. All grades were archived and the replay issued zero provider requests. [Full outcomes, ceiling costs, and paired intervals](witness-shared-rival-ranking-results-v1.json)

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel in a clean source export. With sockets and DNS disabled, 51 targeted tests passed and two full replays matched byte for byte. The control scores, costs, search traces, and funded queues reproduced. The stale seal was rejected and the prospective live plan reproduced byte for byte. Storage Guard measured 6.2 GiB free. The source export, wheel overlay, and publication worktree used the standing 0.2 GiB LAB exception. [Ranking and reservation tests](../tests/unit/test_witness_shared_rival_ranking.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.witness_shared_rival_ranking
python -B -m benchmarks.witness_shared_rival_ranking \
  --execute 8c5ff42d7e20cf694fa3ad1afd065921157c040c21a0c3d948bec30a46b9e958 \
  --out NEW_REPORT.json
```
