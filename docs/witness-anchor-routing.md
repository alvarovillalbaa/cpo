# Choose the wider race from two paid opening replies

The exact score-bound race reproduced the earlier four-anchor result at lower lookup cost. Running it on every episode still exceeded seeded CPO's budget. This replay chooses between the original rotating screen and the score-bound race after the incumbent's first two seeded validation replies. The runner verifies that both routes already pay for both replies in every episode. A choice covers the whole episode, including the original Halving fallback and single independent proof. [Score-bound race](witness-anchor-bounds.md) · [Replay runner](../benchmarks/witness_anchor_routing.py)

An opening rule can send any subset of the zero-, one-, and two-pass groups to the wider race. The first replay tested whole groups. Its cost led to a second sealed comparison that also activates fixed eighths within a group using a stable hash. The blind comparison uses the same hash bins across all episodes. Each fit maximizes mean accuracy across training subjects within their seeded total lookup cost. Lower cost breaks score ties. The primary comparison holds out every seed and both models for each evaluated subject. A separate fit transfers from the other benchmark family. The whole-group and fractional comparisons use the same archive.

The primary rule needs a positive paired lower endpoint against both the original search and the independently fitted blind rule on each cohort. It must also stay within each cohort's realized seeded budget. The training ceiling selects a rule before evaluation. The held-out lookup total measures how well that constraint transfers.

## Results

| Cohort | Original passes / lookups | Whole-group fit passes / lookups | Fractional opening fit passes / lookups | Blind fit passes / lookups | Seeded lookup ceiling |
| --- | ---: | ---: | ---: | ---: | ---: |
| BBH and LMentry | 17,068 / 71,071 | 17,135 / 72,650 | 17,198 / 73,866 | 17,135 / 72,207 | 72,534 |
| MMLU prior subjects | 21,180 / 34,122 | 21,180 / 34,122 | 21,182 / 34,415 | 21,180 / 34,122 | 34,343 |
| MMLU additional subjects | 8,976 / 13,639 | 8,976 / 13,639 | 8,976 / 13,566 | 8,976 / 13,639 | 13,754 |

On BBH and LMentry, the primary rule gained 130 held-out passes and sent 230 episodes to the wider race. It exceeded seeded spend by 1,332 lookups. Its paired 95% interval against the original was 0.000 to +0.710 percentage points. Against the blind rule it was −0.069 to +0.523 points. The most common fitted rule widened one eighth of episodes with zero or one opening pass. Applied uniformly with hindsight on this cohort, that rule gained 61 passes for 973 extra lookups and fit the seeded total. Its cost increased when other fitted rules also operated on held-out subjects.

On the prior MMLU subjects, fractional routing gained two passes and exceeded the seeded budget by 72 lookups. On the additional subjects it matched the original score and saved 73 lookups. The MMLU fits used the same one-eighth rule for episodes with two opening passes. The outside-family fit gained six passes on BBH and LMentry within its seeded total, gained three passes over budget on prior MMLU subjects, and lost one pass over budget on the additional subjects. The primary policy missed the transfer gate. Both search routes paid for the exact same opening pair in all 2,240 episodes. The study made zero provider requests. [Full settings, budgets, paired intervals, and selected rules](witness-anchor-routing-results-v1.json)

A follow-up with stricter training ceilings still missed the transfer gate. The exact hindsight maximum shows how much the two fixed routes could improve if each episode's future cost and score were known. [Budget stress test and route-selection ceiling](witness-anchor-routing-budget.md)

## Reproduce

Use Python 3.12 with the hash-pinned GEPA 0.1.4 wheel in a clean source export. With sockets and DNS blocked, 92 targeted tests passed and two replays matched byte for byte. The fractional replay reproduced the whole-group pilot's selections and totals as well as the sealed original and score-bound controls. The CLI rejected a stale seal and the prospective live plan reproduced byte for byte. Storage Guard measured 6.3 GiB free. The export, wheel overlay, and publication worktree used the standing 0.2 GiB LAB exception. [Subject isolation, cost matching, and route tests](../tests/unit/test_witness_anchor_routing.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.witness_anchor_routing
python -B -m benchmarks.witness_anchor_routing \
  --execute 2606fc1f2b64cd82931ab9554b20713d6069d4b7db0deff9914fe3af20a6f86e \
  --out NEW_REPORT.json
```
