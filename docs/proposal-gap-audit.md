# Where the proposal replay diverged from batched GEPA

Cap-72 CPO used 21,395 fewer lookups than batched GEPA on the eight retrospective transfer panels and ended 26 holdout passes behind. This audit reproduces both deployment paths and measures where the final gap accumulated. Each method keeps its original budget, case splits, proposal blocks, and qualification rule. [Published comparison](expected-cost-proposal-cycle.md) · [Audit runner](../benchmarks/proposal_gap_audit.py)

For every cycle, the audit measures each method’s change in holdout score relative to its own incoming incumbent. Subtracting CPO’s change from GEPA’s produces the cycle’s contribution to the final gap. Both methods start each four-cycle episode with the same prompt, so those contributions sum exactly to the final gap.

When GEPA promotes a different challenger, the audit first checks whether it would beat CPO’s incoming incumbent on the same qualification rows. It then checks strict validation gain and whether CPO’s proposer offered the challenger or search began scoring it. The audit reads unused grades only after both decisions. Its categories describe observed paths and leave the effect of deploying a different prompt unresolved.

## Transfer results

Positive pass changes favor batched GEPA. The eight transfer panels contribute 1,024 paired cycles.

| Outcome | Cycles | GEPA net pass change | Net from cycles with the same incoming prompt |
| --- | ---: | ---: | ---: |
| Both deployed the same prompt | 673 | 0 | 0 |
| GEPA kept its incumbent | 269 | −1 | 0 |
| GEPA challenger failed qualification against CPO’s incumbent | 15 | +24 | 0 |
| GEPA challenger scored below CPO’s incumbent on validation | 6 | +7 | +1 |
| GEPA challenger tied CPO’s incumbent on validation | 19 | −4 | −10 |
| Strict gain and would qualify, never offered | 39 | 0 | 0 |
| Strict gain and would qualify, offered but unopened | 2 | −2 | −2 |
| Strict gain and would qualify, stopped at the search limit | 1 | +2 | +2 |
| **Total** | **1,024** | **+26** | **−9** |

The 802 cycles with a shared incoming prompt favored CPO by nine passes. The 222 cycles with different incoming prompts favored GEPA by 35. In 15 of those cycles accounting for 24 net GEPA passes, the GEPA challenger beat its own incumbent in qualification and would have failed against CPO’s. Among the 39 strict-gain challengers CPO never offered that would have qualified, the positive and negative contributions canceled at 34 passes apiece. The one partially scored challenger with strict gain and a passing qualification widened the observed gap by two passes in its cycle.

On the four development panels, shared-incumbent cycles favored GEPA by 30 passes and divergent cycles favored CPO by 13. The difference across cohorts limits using either subgroup as a predictor. The transfer result directs the next comparison toward incumbent retention after promotion. A trial can carry forward the previous qualified incumbent as a challenger, give both methods the same search and proposal budgets, and require fresh paired evidence before any return. [Panel counts and trace hashes](proposal-gap-audit-results-v1.json)

The follow-up tested one fresh qualification opportunity for the displaced incumbent after each promotion. [Incumbent return replay](proposal-incumbent-return.md)

## Reproduce offline

Use pinned GEPA 0.1.4 and a fresh output path.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.proposal_gap_audit
PYTHONHASHSEED=0 python -B -m benchmarks.proposal_gap_audit \
  --execute e61b51b999c7d8f665ea68e6e2518b7750d363c555bf6548c516dce05eb88ce4 \
  --out NEW_REPORT.json
```

Two clean source replays blocked sockets and DNS and matched byte for byte. Each checked 1,536 cycle pairs and reproduced 24 published panel traces, scores, and lookup totals. Nine focused tests passed. The audit rejected a stale seal and preserved an existing report. Storage Guard measured 9.3 GiB free. The 26.4 MB scratch export was removed under the standing LAB exception. [Tests](../tests/unit/test_proposal_gap_audit.py) · [Verification receipt](proposal-gap-audit-verification-v1.json) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
