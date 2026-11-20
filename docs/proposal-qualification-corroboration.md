# Confirm one-pass promotions on two unused cases

Giving a displaced incumbent another opening restored two prompts on the transfer panels. This replay checks the earlier promotion decision. When the original qualification panel shows exactly one net pass gained, a challenger must gain at least one more pass on a separate two-case panel. Search keeps its 72-lookup ceiling and original proposals. The original qualification decision stands when the gain is at least two or the extra panel is unavailable. [Incumbent return replay](proposal-incumbent-return.md) · [Runner](../benchmarks/proposal_qualification_corroboration.py)

The runner reserves cases before evaluating any prompts. It excludes the final holdout and every training, validation, and original qualification case in the four-cycle episode. Each reserved case is used in at most one cycle. A second exact proof uses cached qualification replies to distinguish a one-pass win from a stronger one. Any additional original-panel replies and all four extra-panel replies are charged. The audit control pays for both checks and applies the original promotion decision. Its search, qualification prefix, and deployment traces match the original CPO arm on every panel.

A full reserve was available in 496 of 512 development cycles and 768 of 1,024 transfer cycles. The two business ethics panels had no spare cases under the original schedule. Their results came entirely from the original decision rule.

## Results

| Policy | Development passes / lookups | Transfer passes / lookups |
| --- | ---: | ---: |
| Original cap-72 CPO | 4,159 / 33,177 | 10,237 / 66,831 |
| Require corroboration | 4,147 / 33,667 | 10,245 / 67,522 |
| Audit without veto | 4,159 / 33,534 | 10,237 / 67,264 |
| Sequential GEPA | 4,139 / 44,944 | 10,236 / 91,649 |
| Batched GEPA | 4,176 / 44,194 | 10,263 / 88,226 |

The extra panel confirmed eight of the 80 one-pass promotions it reviewed on transfer. Enforcing the check gained eight holdout passes and used 691 more lookups than cap-72 CPO. On development it vetoed 59 of the 64 promotions it reviewed and lost 12 holdout passes. The transfer arm finished 18 passes behind batched GEPA and used 20,704 fewer lookups. The joint paired 95% range against both GEPA controls was −70 to +32 passes. The results leave the original promotion rule in place. [Panel outcomes, charges, and paired ranges](proposal-qualification-corroboration-results-v1.json)

## Reproduce offline

Use pinned GEPA 0.1.4 and a fresh output path.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.proposal_qualification_corroboration
PYTHONHASHSEED=0 python -B -m benchmarks.proposal_qualification_corroboration \
  --execute 4756c83368c36c2e6925b3c4f315233f53fd46ceadae405d1cee991b3a88659c \
  --out NEW_REPORT.json
```

Two clean source replays blocked sockets and DNS and matched byte for byte. Each exercised 3,072 experimental cycles and reproduced 48 published control traces. Eight focused tests passed. They included exhaustive checks of all 256 two-prompt outcomes on two qualification and two extra cases, with exact lookup accounting. The runner rejected a stale seal and preserved an existing report. Storage Guard measured 8.6 GiB free. The 26.5 MB scratch export was removed under the standing LAB exception. [Tests](../tests/unit/test_proposal_qualification_corroboration.py) · [Verification receipt](proposal-qualification-corroboration-verification-v1.json) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
