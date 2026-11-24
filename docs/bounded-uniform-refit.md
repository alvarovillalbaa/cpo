# Settle uniform validation by the strongest remaining score bound

The [perfect-challenger screen](perfect-challenger-transfer.md) skips later reads when a challenger needs a perfect score. The new uniform screen works at every incumbent score. It preserves the quoted funded rows and reads each challenger in the original case order. The next read goes to the challenger with the highest possible final score, using the original roster order to settle ties. A failed case lowers that challenger's bound. A complete score settles the winner once it leads every other bound. The incumbent is retained when no upper bound can beat it. [Implementation](../cpo/bounded_uniform_validation.py)

For a fixed case order and a required exact winner score, every rival must be measured through the first prefix whose bound loses to the winner. If the decision is retention, the same argument applies to the incumbent threshold. The screen reads only those necessary prefixes and the complete winner score. Halving uses the existing perfect-challenger implementation, whose shortlist boundaries remain intact. Critical panels use the existing strict validation. Qualification still runs independently with the original nominee and counts.

Use `run_bounded_uniform_cycle` from `cpo.bounded_uniform_validation` with the quoted cycle arguments. The two supported schedules are `uniform` and `successive-halving`.

## Price the same uniform schedule across cohorts

The audit freezes eight-candidate, two-case uniform search in all seven cohorts. It compares the original quote, the perfect-score shortcut, and the new bound order. Every comparison preserves the nomination, complete qualification receipt, and deployment. Each newer method reads a subset of its predecessor's paid replies. The last column gives the original bounded opening's actual lookup budget for that cohort. [Audit runner](../benchmarks/bounded_uniform_price_audit.py) · [Audit receipt](bounded-uniform-price-audit-v1.json)

| Cohort | Held-out passes | Original quote | Perfect-score shortcut | Score bounds | Bounded opening budget |
| --- | ---: | ---: | ---: | ---: | ---: |
| Bounded BBH | 6,358 | 15,348 | 13,928 | 13,550 | 13,421 |
| Bounded LMentry | 6,529 | 15,335 | 14,420 | 13,831 | 15,636 |
| Bounded MMLU | 7,714 | 8,127 | 7,718 | 7,700 | 6,554 |
| Four-case MMLU | 22,365 | 12,939 | 12,650 | 12,644 | 10,591 |
| Tie BBH | 2,118 | 12,646 | 12,201 | 11,983 | 12,521 |
| Tie LMentry | 1,018 | 6,467 | 6,346 | 6,275 | 6,971 |
| Additional MMLU | 7,394 | 8,220 | 7,841 | 7,818 | 6,354 |
| **Pooled** | **53,496** | **79,082** | **75,104** | **73,801** | **72,048** |

The bound order saves 5,281 lookups from the original quote and 1,303 beyond the perfect-score shortcut. The additional savings occur in 293 cycles. It keeps the same 191-pass gain over the bounded opening on bounded LMentry while spending 1,805 fewer lookups. The setting exceeds the task-tuned GEPA upper bound at the larger bounded opening budget in both LMentry cohorts. It fits three cohort budgets overall. Four cohorts still need a different search schedule.

## Refit the episode policies

The refit uses the same 70 discovery panels from 31 tasks, excludes every target task, and keeps each cohort's original bounded opening budget. It compares the earlier constant setting and two-incumbent-probe table before repricing, after repricing, and after re-selecting schedules at the new costs. The run verifies that every original discovery choice and price reproduces before selection. [Refit runner](../benchmarks/bounded_uniform_refit.py) · [Frozen fit](bounded-uniform-refit-v1.json)

Both refits select their earlier schedules. The constant fit remains the bounded opening at 84,043 passes and 67,022 discovery lookups. The two-probe fit still routes one-pass episodes to eight-challenger halving, with the existing perfect-challenger shortcut. Its discovery score stays at 84,026 while spend falls from 61,618 to 60,901. The cheaper quote makes more tables affordable, and the score-first selection retains the bounded opening.

Across the 2,048 archived target episodes, the two-probe fit retains 53,280 passes and uses 68,830 lookups, down from 69,593. It stays within the bounded opening budget in five cohorts. The bounded opening scores 53,308 at 72,048 lookups. On four-case MMLU the two-probe fit still gains 24 passes with a paired 95% range of +7 to +41, and uses 867 fewer lookups than the bounded opening. Task-tuned simple controls still outscore the refit at matched cost in all seven cohorts. Pooled counts describe the archive because some tasks recur.

The uniform screen offers the same decisions at lower cost. The tested episode signals still leave unresolved which schedules to use across tasks. Fresh live superiority remains unverified.

## Reproduce offline

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Omit `--execute` and `--out` to preview a seal. [Benchmark requirements](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.bounded_uniform_price_audit \
  --execute 4f313ae4f1bff29ef49fa392bc99bb135cf8a014cf0321f18e74ac2a4de449dd \
  --out NEW_PRICE_AUDIT.json
PYTHONHASHSEED=0 python -B -m benchmarks.bounded_uniform_refit --fit \
  --execute 5928696d0222710a167713b8f289bb5de0b097eac058326241d17814c0e19487 \
  --out NEW_FIT.json
PYTHONHASHSEED=0 python -B -m benchmarks.bounded_uniform_refit \
  --cohort four-case-MMLU --fitted NEW_FIT.json \
  --execute c60679269c34caeabd479115fa9c9c31dff9821ddd09091276402aa37156563a \
  --out NEW_REPORT.json
```

[Bounded BBH](bounded-uniform-refit-transfer-bounded-bbh-v1.json) · [Bounded LMentry](bounded-uniform-refit-transfer-bounded-lmentry-v1.json) · [Bounded MMLU](bounded-uniform-refit-transfer-bounded-mmlu-v1.json) · [Four-case MMLU](bounded-uniform-refit-transfer-four-case-mmlu-v1.json) · [Tie BBH](bounded-uniform-refit-transfer-tie-bbh-v1.json) · [Tie LMentry](bounded-uniform-refit-transfer-tie-lmentry-v1.json) · [Additional MMLU](bounded-uniform-refit-transfer-additional-mmlu-v1.json)

Forty-five targeted tests passed, including all 4,096 three-row boolean panels at four caps for uniform search. Duplicate pricing audits, fits and target replays matched byte for byte with DNS and outbound sockets blocked. No provider requests were made. Storage Guard measured 9.7 GiB free. The source export, dependency overlay and publication checkout fit the standing 0.2 GiB LAB exception. [Tests](../tests/unit/test_bounded_uniform_validation.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
