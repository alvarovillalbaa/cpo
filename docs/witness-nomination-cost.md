# Defer qualification until validation can nominate a challenger

The [nomination audit](promptolution-stage-headroom.md) found room to improve the shortlist, but even perfect shortlist choice left a lookup gap. This replay tests two ways to reduce the price of reaching a qualified prompt.

- **First repair** checks up to two incumbent validation cases and tests up to four challengers on the first miss. It nominates the first repair in roster order. Two arms compare the same witness screen before and after the incumbent qualification precheck.
- **Original screen first** retains packaged uniform and halving validation and defers the incumbent qualification precheck until validation produces a nominee. A perfect incumbent on qualification still closes the gate. The fitted opening continues to precheck first because the position of the first qualification miss selects its screen. Critical validation keeps the original order. The full-roster arm defers only when the roster fills the original challenger limit of the selected screen.

The verifier checks that changing the precheck order reproduces the same nominees, deployments, and feedback transitions for each pair of arms. All promotions still pass the exact, disjoint qualification. Lookup counts include validation paid before a precheck rules out deployment. [Benchmark](../benchmarks/witness_nomination_cost.py)

## Results

Across 2,048 language episodes, moving qualification after first-repair validation saved 6,745 lookups at the same 52,265 held-out passes. That witness policy lost 1,080 passes relative to packaged feedback. Across 64 Promptolution episodes, it lost 159 passes for feedback and 185 for settled CPO. The larger savings from replacing the screen came with a clear accuracy cost.

Using the original screen first saved 4,465 lookups on the language archives. It avoided 6,644 qualification lookups and added 2,179 validation lookups. The same change added 35 lookups for Promptolution feedback and 93 for settled CPO. Both orders reproduced the packaged final prompts. This difference motivated the full-roster guard. [Matched comparisons and paid trace hashes](witness-nomination-cost-v1.json)

| Archive | Packaged passes / lookups | Full-roster guard passes / lookups |
| --- | ---: | ---: |
| Language feedback, seven cohorts | 53,345 / 68,582 | 53,345 / 64,117 |
| Promptolution feedback | 3,885 / 2,348 | 3,885 / 2,348 |
| Promptolution settled | 3,924 / 2,455 | 3,924 / 2,455 |

The guard retains the entire 6.5% language lookup saving and ties the Promptolution costs. It uses the existing eight-challenger uniform and feedback-halving widths and the four-challenger opening-halving width. The same three language cohorts exceed the subject-tuned GEPA ceiling at the new cost. The guard was designed after seeing the archive cost contrast, so these scores are exploratory. It is available in the benchmark as a candidate for prospective testing. Live superiority remains unverified.

## Reproduce offline

Use the frozen Promptolution corpus and GEPA 0.1.4 environment. The language data and frozen receipts are read from the repository.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.witness_nomination_cost \
  --corpus PREDICTIONS.json \
  --execute e41709fc983aa7e49db9b636be97deecc2f571d2c58d61c8bb2394f7ba6e4c25 \
  --out /tmp/cpo-witness-nomination-cost.json
```

Two network-disabled replays produced byte-identical receipts. All 101 focused tests passed, including the two precheck orders, the protected-panel fallback, and the roster-width guard. Storage Guard measured 10.0 GiB free. The disposable source, pinned wheel overlay, corpus copy and publication checkout fit the standing 0.2 GiB LAB exception. Teardown was verified. [Tests](../tests/unit/test_witness_nomination_cost.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
