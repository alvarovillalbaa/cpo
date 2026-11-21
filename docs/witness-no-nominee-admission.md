# Try one paid candidate when search returns no nominee

The search audit found an already-evaluated candidate with higher held-out accuracy in 280 of 293 MMLU episodes that ended without a nominee. This replay keeps every paid search and every existing nomination fixed. Only after a no-nominee stop does it consider submitting one previously evaluated candidate to its assigned independent proof. The packaged admission API runs that proof with the original cap of 24 lookups. Existing proofs and all new proof calls are charged. [Search coverage audit](witness-unread-nominee-probe.md) · [Admission API](funded-admission.md) · [Runner](../benchmarks/witness_no_nominee_admission.py)

The broad rule takes the highest smoothed pass rate. A narrower rule also requires three paid grades and a smoothed rate above the incumbent. Two matched rules require a net validation gain of at least one or two on shared paid cases. They rank qualifying candidates by the paired margin divided by the number of paired cases plus two, then by smoothed pass rate. Candidate order resolves ties. When a rule declines or its proof fails, the incumbent stays. The other benchmark family selects a rule by promotions within original seeded spend, with lower spend breaking ties. The held-out gate requires a positive paired lower endpoint against the full single proof within the original seeded cost in each cohort.

After freezing those choices, the audit prices all paid candidates on their assigned proof panels. A hindsight calculation takes at most one independently qualifying improvement from each no-nominee episode. Its budget is the cohort's realized savings from ordering the original proofs by expected reads. This ceiling uses complete archived replies, exact proof costs, and held-out scores.

## Results

| Cohort | No-nominee episodes | Stronger paid candidate | Stronger paid candidate that passed independent proof | Available lookups | Hindsight added passes / lookups |
| --- | ---: | ---: | ---: | ---: | ---: |
| BBH and LMentry | 166 | 156 | 127 | 1,463 | 632 / 1,460 |
| MMLU prior subjects | 229 | 218 | 159 | 221 | 207 / 221 |
| MMLU additional subjects | 64 | 62 | 46 | 115 | 46 / 112 |

On MMLU, 205 of 293 no-nominee episodes had a stronger paid candidate that could pass independent proof. No MMLU candidate in those episodes had a positive net gain on shared paid validation cases. An ideal selector with hindsight could buy 253 additional MMLU passes using 333 of the 336 lookups saved by expected-read ordering.

BBH and LMentry training selected the supported-rate rule for MMLU. It ran 22 proofs and added 23 pooled passes for 370 lookups. It exceeded the original seeded cost on the prior MMLU subjects by 96 lookups, and its paired interval ranged from −0.002 to +0.080 percentage points there. The additional subjects produced an exact tie. MMLU training selected the full single proof for BBH and LMentry. The cross-family gate failed. [All routes, costs, and paired ranges](witness-no-nominee-admission-results-v1.json)

## Reproduce

Use a clean export with Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. With DNS and sockets blocked, 44 targeted tests passed and two full replays matched byte for byte. The original no-nominee counts, paid reachability, single-proof costs, and scores reproduced. The CLI rejected a stale seal, and the prospective live plan reproduced byte for byte. Storage Guard measured 4.9 GiB free. The source export, overlay, and publication worktree fit the standing 0.2 GiB LAB exception. [Ranking and budget tests](../tests/unit/test_witness_no_nominee_admission.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.witness_no_nominee_admission
python -B -m benchmarks.witness_no_nominee_admission \
  --execute c1c8bf711d342d54501d166b3d0f82988ee3085d057c31933a8d383d04464b53 \
  --out NEW_REPORT.json
```
