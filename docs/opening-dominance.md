# Prove an opening rewrite wins before scoring every row

Pass `certify_dominance=True` to `run_opening_screen_cycle` to try the proof before ordinary adaptive opening search. It reads the incumbent's screen first, then verifies that the supplied rewrite preserves every observed incumbent pass. One new pass proves that the rewrite's pass set is strictly larger. With field credit enabled, a strictly positive lower bound on matched-field gain can also settle a tie. The proof uses the worst possible remaining matched-field loss, so it can finish while some rewrite replies are still unknown.

A successful proof nominates the same rewrite as a complete adaptive opening on fixed replies. The full-panel gate still enforces strict net improvement, family nonregression, and critical case protection. Independent qualification still follows that gate. If the proof fails, ordinary search reuses the paid observations. Speculative reads can add cost on an individual path. The proof runs only when all three opening prompts fit within the screen budget and the original full-panel reserve remains available.

## Recorded Sol replay

All 240 selections and admission decisions matched the previous CPO policy. CPO and fixed-opening GEPA selected the same prompt on every path and agreed on all 480 held-out scores. Both passed 382. [Grouped replay charges and matched scores](../benchmarks/data/opening-dominance-cost-terms-v1.json)

| Policy | Attributed search reads | Estimated cost at archived rates |
| --- | ---: | ---: |
| CPO with certified full validation | 1,398 | $20.842344 |
| CPO with the opening dominance proof | 1,383 | $19.915032 |
| Fixed-opening GEPA | 1,920 | $23.456712 |

The dominance proof saved **15.10%** against GEPA at the original attributed prices. The conservative lower bound with separate prices per policy was **12.43% pooled** and **11.53% on outage**. Both clear the 10% gate. Outage went from 549 to 486 search reads. Ticket added 48 reads and its estimated cost fell from $4.899672 to $4.680000. Across the archive, 45 paths read more than the preceding CPO policy and 40 cost more. The savings are aggregate results.

A one-row screen also reduced cost but lost a recorded outage pass. The dominance proof keeps the existing screen and preserves its decision on fixed replies. Fresh models, costs, and qualification still require prospective evidence.

```sh
python -B -m benchmarks.certified_opening_cost_sensitivity \
  benchmarks/data/opening-dominance-cost-terms-v1.json
python -m pytest -q tests/unit/test_opening_dominance.py
```

The test compares 39,366 fixed field-outcome matrices and critical masks through the real opening cycle. It verifies that the selected prompt and qualification decision match the preceding CPO policy and that every paid read stays within the cap. [Proof](../cpo/opening_dominance.py) · [Tests](../tests/unit/test_opening_dominance.py)
