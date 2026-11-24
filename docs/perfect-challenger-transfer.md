# Skip later reads when the quoted screen requires a perfect challenger

The [episode-admission audit](episode-admission-transfer.md) showed that a wider quoted screen can improve decisions at a higher lookup cost. This change shortens its validation work while preserving those decisions. It uses the same funded rows and shortlist limits as quoted uniform or halving validation. The independent qualification proof receives the same nominee and exact validation counts. [Implementation](../cpo/perfect_challenger_screen.py)

When the incumbent passes all but one funded case, the challenger needs a perfect score to beat it. A challenger failure settles that prompt's eligibility immediately. Among perfect prefixes, ties follow the original roster order. The new screen reads a candidate's prefix before reading later candidates, tracks how many earlier candidates filled each shortlist, and stops at the first eligible perfect candidate. A candidate cannot regain a seat that was already filled by an earlier perfect prefix at that round. Critical panels and other incumbent scores use the original quoted behavior. The evaluator still returns stable boolean grades on validation.

Use `run_perfect_challenger_cycle` from `cpo.perfect_challenger_screen` with the same arguments as the quoted cycle. It supports `schedule='uniform'` and `schedule='successive-halving'`. The existing default remains available.

## Offline replay

The audit keeps the original 2,048 episodes and compares three schedules. The combined rule includes its original training probes and retention. The wider-search-only control keeps the original wider schedule for one-pass episodes and leaves the others on the bounded opening. The common schedule is chosen once per cohort using the earlier hindsight frontier. The replay makes that choice independent of the new prices, so the comparison isolates the ordering change.

Every replayed cycle preserves the nomination, full qualification receipt and deployment. The paid reply set is a subset of the original reply set. All saved lookups come from validation. Each cell below gives passes and lookups before and after the change. [Benchmark](../benchmarks/perfect_challenger_transfer.py)

| Cohort | Combined passes | Combined lookups | Wider-only passes | Wider-only lookups | Common passes | Common lookups |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Bounded BBH | 6,335 | 13,212 → 12,906 | 6,362 | 16,465 → 16,159 | 6,354 | 11,038 → 10,617 |
| Bounded LMentry | 6,313 | 15,502 → 15,351 | 6,379 | 17,392 → 17,241 | 6,529 | 15,335 → 14,420 |
| Bounded MMLU | 7,721 | 5,275 → 5,170 | 7,723 | 8,101 → 7,996 | 7,719 | 6,503 → 6,452 |
| Four-case MMLU | 22,393 | 9,797 → 9,724 | 22,398 | 12,807 → 12,734 | 22,389 | 9,624 → 9,587 |
| Tie BBH | 2,131 | 13,165 → 13,123 | 2,139 | 13,916 → 13,874 | 2,145 | 12,521 → 12,521 |
| Tie LMentry | 991 | 7,042 → 7,030 | 990 | 7,257 → 7,245 | 1,018 | 6,467 → 6,346 |
| Additional MMLU | 7,396 | 5,600 → 5,526 | 7,397 | 7,902 → 7,828 | 7,398 | 6,354 → 6,354 |
| **Pooled** | **53,280** | **69,593 → 68,830** | **53,388** | **83,840 → 83,077** | **53,552** | **67,842 → 66,297** |

Both episode rules save 763 reads across 165 cycles because they share the same wider-search branch. The common schedules save 1,545 reads across 461 cycles. In bounded LMentry, eight-challenger uniform search over two rows saves 915 reads, about 6% of its original total. All seven common schedules remain within the bounded opening's budget. The combined rule still fits five cohorts, and the wider-only rule exceeds all seven budgets. Pooled counts describe the archive because cohorts reuse some tasks.

The receipts price native GEPA and simple schedules at the revised actual spend. The common hindsight choice exceeds the task-tuned native GEPA upper bound in six cohorts and exceeds the affordable task-tuned simple point score in both LMentry cohorts. Those settings were selected with target outcomes. The evidence establishes a lossless reduction in recorded reads for the fixed choices. Fresh live superiority and an equally accurate task-blind schedule chooser remain unverified.

## Reproduce offline

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Omit `--execute` and `--out` to preview a seal. [Benchmark requirements](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.perfect_challenger_transfer \
  --cohort bounded-LMentry \
  --execute b2104a980d18b9dc00e47ebb0ff9abf0e3632394b0d89262e84605ae0f321048 \
  --out NEW_REPORT.json
```

[Bounded BBH](perfect-challenger-transfer-bounded-bbh-v1.json) · [Bounded LMentry](perfect-challenger-transfer-bounded-lmentry-v1.json) · [Bounded MMLU](perfect-challenger-transfer-bounded-mmlu-v1.json) · [Four-case MMLU](perfect-challenger-transfer-four-case-mmlu-v1.json) · [Tie BBH](perfect-challenger-transfer-tie-bbh-v1.json) · [Tie LMentry](perfect-challenger-transfer-tie-lmentry-v1.json) · [Additional MMLU](perfect-challenger-transfer-additional-mmlu-v1.json)

Forty-three targeted tests passed, including all 4,096 binary validation matrices for three challengers over three cases, at five caps and both schedules. Duplicate archive replays matched byte for byte with DNS and outbound sockets blocked. No provider requests were made. Storage Guard measured 9.7 GiB free. The temporary source export, dependency overlay and publication checkout fit the standing 0.2 GiB LAB exception. [Tests](../tests/unit/test_perfect_challenger_screen.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
