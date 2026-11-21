# Use disjoint paid history to nominate after a stalled search

Shorter proof reservations left the MMLU result unchanged. This replay tests whether earlier validation can identify a nominee when the original search found none. Every original search, nomination, and proof is preserved. The history is local to one subject and one model and starts empty. Only paid validation pairs from prior episodes enter it. [Shortened proof comparison](witness-short-admission-credit.md) · [Runner](../benchmarks/witness_history_admission.py)

At a stalled search, both history rules consider only candidates already evaluated in that episode. They exclude all of its training, validation, qualification, and held-out case IDs. The margin rule ranks by positive net wins on at least three remaining paired cases, normalized by the number of cases plus two. The confirmation rule keeps the original supported-rate candidate if it meets that same test. Current paid grades enter history after the offer is chosen.

Each queue runs in scheduled episode order with the same cohort budget and 24-lookup proof reservation. A separate exact proof on the candidate's assigned panel still decides deployment. The original direct queue is the matched comparator. Promotion counts and cost on the other family select the transferred rule. A positive paired lower endpoint against the full single proof is required in every cohort.

## Results

| Cohort | Single proof passes / lookups | Direct queue passes / lookups | Historical margin passes / lookups | History confirmation passes / lookups |
| --- | ---: | ---: | ---: | ---: |
| BBH and LMentry | 17,068 / 71,071 | 17,146 / 72,121 | 17,068 / 71,071 | 17,068 / 71,071 |
| MMLU prior subjects | 21,180 / 34,122 | 21,190 / 34,323 | 21,203 / 34,323 | 21,180 / 34,122 |
| MMLU additional subjects | 8,976 / 13,639 | 8,976 / 13,692 | 8,979 / 13,655 | 8,976 / 13,639 |

None of the 166 stalled BBH and LMentry episodes had a disjoint historical pair for an eligible candidate. Positive margins with at least three pairs were available in 15 of 229 stalled episodes on the prior MMLU subjects and one of 64 on the additional subjects. Historical margin funded ten and one proofs, respectively, with two and one promotions. History confirmation produced zero offers in all three cohorts.

Historical margin gained 13 passes at the same lookup count on the prior MMLU subjects and three passes with 37 fewer lookups on the additional subjects. Its paired 95% intervals against the direct queue were −0.067 to +0.043 percentage points and 0.000 to +0.047, respectively. Both outside-family fits selected the direct queue. Its paired lower endpoint against the single proof was positive only on BBH and LMentry. The overall gate remained unmet. These estimates use archived grades, with zero new provider requests. [Complete paired results and offer counts](witness-history-admission-results-v1.json)

## Reproduce

Use Python 3.12 with the hash-pinned GEPA 0.1.4 wheel in a clean source export. With outbound sockets and DNS disabled, 40 targeted tests passed and two complete replays matched byte for byte. The existing search and proof controls reproduced their counts and the direct queue reproduced its funded trace. The stale seal was rejected and the prospective live plan reproduced byte for byte. Storage Guard measured 6.4 GiB free. The export, pinned overlays, and publication worktree used the standing 0.2 GiB LAB exception. [Case exclusion and grade consistency tests](../tests/unit/test_witness_history_admission.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.witness_history_admission
python -B -m benchmarks.witness_history_admission \
  --execute 927db6d1bdf2e6a33648b89ba177efbc199011c1b913ff0c508b62c0336fc5ae \
  --out NEW_REPORT.json
```
