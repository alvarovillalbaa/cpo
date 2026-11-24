# Compare both CPO episode runners with native GEPA

This development protocol exercises the packaged settled and qualification-feedback runners against sequential and same-parent batched GEPA 0.1.4. One shared responder drafts four rewrite and repair pairs per cycle. Every arm receives the same ordered roster, up to eight challengers. A malformed or duplicate pair is dropped for every arm. Each of the three tasks runs three cycles and carries forward only prompts that pass independent admission. [Portable runner](../benchmarks/settled_episode_prospective.py) · [Sealed development manifest](settled-episode-prospective-plan-v1.json)

The study reuses the unstarted witness experiment's training, admission, and holdout cases in their original roles. Its first rehearsal found that the six-lookup CPO schedule couldn't nominate with critical cases in the screening panel. To exercise the measured quoted schedules, the sealed version gives all four arms six new disjoint, noncritical validation cases per cycle. Admission and holdout preserve their original critical flags. The reserved confirmation cases stay out of development requests. [Prior witness protocol](grounded-witness-episode.md)

CPO uses its existing validation caps of up to 19 lookups per cycle plus two opening training probes per task. Both GEPA controls receive up to 32 evaluation lookups per cycle over their disjoint training cases and the same six validation cases. That allowance funds a full batched round after reading the incumbent. Each method can use up to eight admission replies per cycle. All methods charge actual distinct search requests and logical uses, with shared drafting attributed to each arm. Final development scoring runs on 18 separate cases per task with two matched repeats.

The feedback candidate must reach 27 of 36 passes on each task, preserve matched critical decisions, and match or improve each comparator's task score. For each control it must add eight passes in aggregate or preserve every case score and save at least 10% of search requests. The gate applies under both request counts.

| Role | Planned request ceiling | Scripted physical requests |
| --- | ---: | ---: |
| Shared drafting | 36 | 36 |
| Evaluation | 930 | 188 |
| Admission | 288 | 59 |
| Development scoring | 540 | 252 |
| **Total** | **1,794** | **535** |

## Offline rehearsal

All four arms completed the 72-candidate fixture. Both native GEPA controls evaluated challengers on every task. The feedback runner exercised each follow-up schedule, including one deliberate zero-read cycle. Two scripted runs and the exact journal replay produced identical archives. Each optimizer scored 36 of 36 scripted passes per task. Feedback used 127 attributed search requests, versus 126 for settled CPO, 190 for sequential GEPA, and 250 for batched GEPA. The fixture failed the full gate against settled CPO. These scripted scores and request counts verify the harness and its gate. [Rehearsal receipt](settled-episode-prospective-rehearsal-v1.json)

Run from a clean export of the sealed source revision with Python 3.12 and the hash-pinned GEPA 0.1.4 benchmark wheel.

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.settled_episode_prospective
python -B -m benchmarks.settled_episode_prospective \
  --fixture 3e34abd7a7d77514c48c5bbdd8e4bcffe676ece55c89542b0155d8b298501775 \
  --out settled-development-fixture
python -B -m benchmarks.settled_episode_prospective \
  --replay settled-development-fixture --out settled-development-replay
```

Forty-nine focused tests passed. The tests cover role disjointness, critical admission and scoring, both native controls, duplicate drafts, stale seals, and a lost reply that leaves its intent in the journal. Storage Guard measured 9.3 GiB free. The disposable source, wheel overlay, fixtures, and publication checkout fit the standing 0.2 GiB LAB exception and were removed. No provider requests were made. [Tests](../tests/unit/test_settled_episode_prospective.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)

The portable entry point accepts an injected responder. Live execution requires a separately sealed provider adapter and cost quote for this protocol. Independent confirmation and fresh performance remain unverified.
