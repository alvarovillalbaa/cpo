# Keep the starting prompt until a single final deployment

The priced reachability audit found 85 losses against GEPA where a better fresh path fit CPO’s observed spend. Eighty of those matches required just one move from the start. The reserved regression guard later recovered some losses from harmful moves, and lost more holdout passes on other episodes. This replay tests a different trajectory that keeps the same comparator while collecting qualified challengers. [Priced reachability](priced-gate-reachability.md) · [Reserved regression guard](reserved-regression-guard.md)

Both variants keep the original start through the first three cycles. Fresh search uses the existing routed selector and proposal order. A candidate enters the bank only after a strict validation gain, a strict independent qualification gain, and no qualification loss in either half. The bank ranks candidates by the paid lower bound on their qualification gain, breaking ties by fewer replies and then recency.

- **Reconfirm** tries the highest-ranked banked candidate in the existing final archive slot. It must pass the same qualification gate on the final panel, which is separate from its first panel. If the archive check fails, the original fresh search can still nominate a prompt from the final roster.
- **Paid proof** runs fresh search in all four cycles and deploys the highest-ranked qualified candidate from the bank. It uses the paid proof from the candidate’s first successful qualification.

Both methods retain the original lookup ceilings, proposal blocks, four qualification panels, and final holdout. Ordinary per-cycle deployment, retaining the start, official sequential and batched GEPA at cap 52, and batched GEPA at cap 47 form the controls. The replay uses 896 seeded episodes on 28 archived model and subject panels. Its gate requires 10% savings against both cap-52 controls and a nonnegative lower endpoint of the joint paired case range. [Runner](../benchmarks/deferred_adoption.py)

## Results

Each cell gives final holdout passes and paid search plus qualification lookups.

| Method | Llama and Mistral | Gemma and Flan |
| --- | ---: | ---: |
| Retain start | 17,617 / 0 | 17,404 / 0 |
| Original per-cycle CPO | 17,724 / 49,330 | 17,435 / 35,496 |
| Defer and reconfirm | 17,646 / 47,449 | 17,401 / 34,373 |
| Defer and use the paid proof | 17,669 / 46,867 | 17,407 / 33,981 |
| Batched GEPA, cap 47 | 17,687 / 45,679 | 17,407 / 31,608 |
| Batched GEPA, cap 52 | 17,694 / 57,271 | 17,422 / 40,184 |
| Sequential GEPA, cap 52 | 17,721 / 81,537 | 17,409 / 60,951 |

The paid-proof arm saved 3,978 lookups and lost 83 net holdout passes versus ordinary CPO. The reconfirm arm saved 3,004 lookups and lost 112 passes. Early cycles banked 185 qualifying candidates across both cohorts. The final archive check ran in 164 episodes and passed in 36. On the 85 audited losses with affordable fresh paths, the paid-proof and reconfirm arms recovered six and two comparisons respectively. They also recovered 44 and 74 of the 109 losses where the starting prompt was sufficient. Counts treat each GEPA comparison separately. [Panel-level costs and recoveries](deferred-adoption-results-v1.json)

Both methods saved more than 10% of lookups against both cap-52 GEPA controls. The reconfirm arm failed the Llama and Mistral quality gate, with a joint paired range of −132 to −24. Its Gemma and Flan range was −59 to +13. The paid-proof ranges were −115 to +6 and −61 to +28. Keeping the starting prompt fixed avoided some harmful moves on these panels. The resulting trajectory lost more passes than it recovered. CPO retains per-cycle adoption. These are comparisons on supplied recorded prompt pools.

The subsequent audit found that 50 of the 85 affordable-path losses stopped at screening without a paid gain witness. [Challenger-stage attribution](affordable-challenger-attribution.md)

## Reproduce

Use pinned GEPA 0.1.4 and a fresh output path. Two source-export replays matched byte for byte and reproduced 140 published panel-control records with sockets and DNS blocked. Three focused tests verified the anchor, paid ranking, and final reconfirmation. The CLI rejected a stale seal and preserved an existing report. Storage Guard measured 14.1 GiB free. The 20.6 MB temporary overlay was removed under the standing LAB exception. Fresh model performance remains unverified. [Tests](../tests/unit/test_deferred_adoption.py) · [Verification receipt](deferred-adoption-verification-v1.json) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.deferred_adoption \
  --execute 8bdba5817b492c4eaa21b406b1f76c26d687b7ea28169b2db10ef920ef51a219 \
  --out NEW_REPORT.json
```
