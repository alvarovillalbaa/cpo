# Reuse paid incumbent replies under a tight search cap

At a tight cap, the seeded screen reserves logical slots to read the incumbent and finish its first viable challenger. The official paid-cap GEPA controls can reinvest cache savings within a cycle. This replay tests the corresponding change for seeded CPO. Every exact incumbent reply already paid for on the current validation panel funds one additional logical slot. It still takes a fresh lookup to read an uncached pair, and the existing archive debit still reduces the cycle's paid search budget. [Seeded selector](../cpo/lazy_incumbent.py) · [GEPA paid-cap protocol](gepa-paid-cap-transfer.md)

The credit uses the same prompt and case within the same episode. The search keeps its first-gain order and still requires a strict validation certificate followed by independent paired qualification. Each cycle may read at most the whole incumbent panel plus the challenger reserve. An unread incumbent reply leaves its matching slot unused. The adapter checks the paid ceiling before every cache miss. Neither qualification replies nor another method's replies fund the credit. [Benchmark runner](../benchmarks/paid_incumbent_credit.py)

The replay uses the eight archived Gemma and Falcon panels from the MMLU cost frontier and the 12 archived Flan-UL2 and Mixtral panels from the low-budget replication. Each panel uses the original 32 seeded four-cycle episodes, fixed holdout, proposal blocks, and recency archive. The two cohorts were available before this intervention. The lookups are counts of distinct recorded evaluations, including qualification. [MMLU cost frontier](independent-mmlu-cost-frontier.md) · [Low-budget replication](low-budget-transfer.md)

## Results

| Method | Gemma and Falcon passes / lookups | Flan-UL2 and Mixtral passes / lookups |
| --- | ---: | ---: |
| Retain start | 8,918 / 0 | 18,799 / 0 |
| Seeded CPO, cap 28 | 8,963 / 14,084 | 18,813 / 19,602 |
| CPO with incumbent credit, cap 28 | 8,961 / 15,121 | 18,812 / 20,722 |
| Seeded CPO, cap 36 | 8,967 / 20,861 | 18,842 / 30,989 |
| CPO with incumbent credit, cap 36 | 8,971 / 21,057 | 18,842 / 31,219 |
| Batched GEPA, cap 39 | 8,920 / 11,884 | 18,801 / 17,563 |
| Batched GEPA, cap 44 | 8,975 / 21,282 | 18,866 / 30,649 |

At cap 28, credit raised the number of fresh validation certificates from 335 to 355 across 640 episodes. The variant used 2,157 more paid lookups and scored three fewer final passes. The two episodes with a changed holdout score both lost passes. At cap 36, one Gemma/Falcon episode gained four passes, and the Flan-UL2/Mixtral holdout totals tied. The credited cap-36 setting still finished below batched GEPA at cap 44 on both cohorts. These results leave the default search budget unchanged. [Sealed per-panel scores and costs](paid-incumbent-credit-results-v1.json)

All 28 available seeded reference traces reproduced. Two network-blocked runs per cohort produced identical reports. The contract test checked the paid cap, strict gain, and critical-case preservation on 20,480 combinations of binary outcomes, cached incumbent cases, and budgets. The CLI rejected a stale seal before creating an output. Storage Guard measured 13.7 GiB free, and the standing LAB exception covered 9.4 MB of disposable verification files. Teardown was verified. Fresh prompt generation and provider costs remain unverified. [Budget contract test](../tests/unit/test_paid_incumbent_credit.py)

## Reproduce

Use pinned GEPA 0.1.4. Preview the phase seal, then rerun with the seal and a fresh output path. The other phase is `development`.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.paid_incumbent_credit --phase replication
PYTHONHASHSEED=0 python -B -m benchmarks.paid_incumbent_credit \
  --phase replication --execute b8ae24bd644c130c11490f252b0d56f37452503cd05427e0ee8191b2d1af98c9 \
  --out NEW_REPORT.json
```
