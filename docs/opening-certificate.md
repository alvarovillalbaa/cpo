# Certify a perfect opening rewrite with fewer incumbent evaluations

`search_with_opening_certificate` tests the first rewrite in a supplied opening pair. If the rewrite passes every validation case, one observed incumbent miss proves strict gain, nonregression in every family, and preservation of every critical pass. The shortcut reads the original critical prefix and finds a witnessed gain before completing the rewrite. If the proof fails, ordinary search reuses the replies already bought under its original evaluation cap. [Package function](../cpo/opening_certificate.py)

Use the same search arguments and a supplied `ProposalPair`.

```python
from cpo.opening_certificate import search_with_opening_certificate

result = search_with_opening_certificate(
    incumbent, train, validation, evaluate, propose,
    opening_pair=opening_pair,
    metric_limit=56,
    rounds=6,
    train_per_round=2,
    adaptive=True,
    field_credit=True,
)
```

The function returns a search result. Use independent qualification before deploying its selected prompt. Equivalence assumes fixed valid replies for a prompt and case. The certificate can change the order in which a live evaluator sees requests.

## Recorded Sol token costs

The previous audit found a pooled CPO cost advantage but missed the 10% savings requirement for tied ticket-routing scores against sequential GEPA. Replaying the certificate on the same archived receipts cleared that gap. [Baseline and costing method](recorded-opening-token-cost.md)

| Ticket routing | CPO with full incumbent validation | CPO with opening certificate | Sequential GEPA | Certified savings versus GEPA |
| --- | ---: | ---: | ---: | ---: |
| First seed set | $2.248032 | $1.960584 | $2.490840 | 21.3% |
| Second seed set | $2.240064 | $1.938360 | $2.472456 | 21.6% |

Across 240 archived trials, the certificate saved 374 incumbent evaluations and preserved every selected prompt, proposal trace, and held-out result. All 12 task-by-seed-set comparisons against sequential and batched GEPA cleared the historical cost gate, with zero matched critical losses. This is a test on fixed recorded replies and proposal graphs. Fresh provider quality and spend remain unverified.

Two offline replays matched exactly. The shortcut also matched ordinary search on 6,144 exhaustive input patterns with both the original and the current released optimizer. In the original GEPA research workspace, `python -B run_recorded_opening_cost.py --opening-certificate --out NEW_REPORT.json` reproduces the historical report with SHA-256 `b7118b84e05eff7ec51a7b86e7d243dd95853652a68cd883745bc482d240d2c2`. [Tests](../tests/unit/test_opening_certificate.py)
