# Audit the paid rivals available for a second proof

Reserving room for a second proof gave MMLU more attempts and fewer promotions. This audit freezes the paid search, first proof, and switch decisions of the reserved-futility replay across all 2,240 episodes. For actual second attempts, it enumerates the rivals with paid search grades and prices each rival's exact proof on its assigned independent panel. That proof uses the same panel selection and tie rule as the original retry. [Reservation comparison](witness-proof-split.md) · [Audit runner](../benchmarks/witness_rival_capacity.py)

Held-out scores affect only the retrospective comparison. Each second attempt records the furthest point any improving rival reaches. An improvement may be absent from the enrolled roster, present only among unread rivals, rejected by the complete proof, beyond the remaining cap, or feasible. Unread rivals are counted from the archive and receive no proof. A rival improves on the start when it passes more of the held-out cases.

Two hindsight comparisons pick the best certified paid rival or retain the start. One uses only the reads actually spent on that episode's second proof. The other can spend up to the remaining portion of the joint cap. Both preserve first-proof spend and the observed result on episodes that made no retry. Their scores bound what a different ranking could achieve on this archived schedule. A runtime selector has no access to the held-out scores used to construct these bounds.

## Results

| Furthest any improving rival reached | BBH and LMentry | MMLU prior subjects | MMLU additional subjects |
| --- | ---: | ---: | ---: |
| No improving enrolled rival | 30 | 22 | 7 |
| Improving rivals were unread | 58 | 24 | 17 |
| All improving paid rivals failed proof | 131 | 114 | 69 |
| An improving paid rival qualified beyond the remaining cap | 233 | 129 | 51 |
| An improving paid rival qualified within the remaining cap | 155 | 17 | 9 |
| Total second attempts | 607 | 306 | 153 |

MMLU had 389 second attempts with at least one improving paid rival. Only 26 had an improving rival that qualified within the remaining budget. Of the other attempts with an improving paid rival, all such rivals failed the independent proof in 183 and a certificate required more than the remaining allowance in 180. The published retry selected an improving rival in five cases. Within the reads already spent, a better ranking could beat both the published outcome and retention in at most 20 cases.

| Cohort | Single proof passes / lookups | Published reserved retry passes / lookups | Best at realized second-proof spend | Best within remaining cap |
| --- | ---: | ---: | ---: | ---: |
| BBH and LMentry | 17,068 / 71,071 | 17,121 / 75,764 | 17,665 / 70,611 | 17,791 / 70,876 |
| MMLU prior subjects | 21,180 / 34,122 | 21,174 / 35,910 | 21,228 / 32,652 | 21,228 / 32,652 |
| MMLU additional subjects | 8,976 / 13,639 | 8,989 / 14,759 | 9,009 / 13,104 | 9,012 / 13,134 |

The best same-spend hindsight choice gains 81 pooled MMLU passes over the full single proof. The remaining-cap choice adds three more. Hindsight spend drops because it can keep the start without paying for a failed second proof. On this schedule, improving MMLU ranking alone has fewer opportunities than improving admission feasibility. The table includes both possible selection gains and the savings from perfect knowledge of when to skip a retry. [Full report and episode trace hashes](witness-rival-capacity-results-v1.json)

The next replay found that changing only the order of incumbent and rival reads could free room for an improving certificate in 11 of the 180 MMLU episodes. Another 155 needed a different case order. [Proof ordering comparison](witness-rival-order.md)

## Reproduce

Use a clean export with Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. With DNS and sockets blocked, 27 targeted tests passed and two offline audits matched byte for byte. The CLI rejected a stale seal, all five original arms reproduced down to panel traces, and the prospective development plan reproduced byte for byte. The audit made zero provider requests. Storage Guard measured 5.8 GiB free. The export, overlay, and publication worktree fit the standing 0.2 GiB LAB exception. [Audit tests](../tests/unit/test_witness_rival_capacity.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.witness_rival_capacity
python -B -m benchmarks.witness_rival_capacity \
  --execute 611b523fd567be78aa9a9919ec925d1b788fb1920087782e4791c1e7435f10bd \
  --out NEW_REPORT.json
```
