# Strengthen qualification for CPO's second-case repairs

The [case-switch audit](interleaved-validation-transfer.md) attributed the bounded BBH loss to newly accepted second-case repairs. This experiment keeps the same validation switch and strengthens qualification only when the original proof would promote a nominee that passed the second validation case after the incumbent failed it. A nominee can be held to a **two-pass net gain** on independent qualification, or required to **preserve every incumbent qualification pass** while retaining the original one-pass gain requirement. Ordinary opening-case promotions and original rejects keep their original proof. [Cycle and proof reuse](../cpo/second_case_qualification.py)

Both gates reuse every paid reply in its original position in the qualification receipt. The stronger proof reads only previously unread prompt-and-case pairs and stays within the original eight-read cap on the four-case qualification panel. Validation keeps its nine-lookup cap. The archive benchmark checks the promotion decisions against all independent qualification grades after the run. That check has no effect on routing or promotion. [Replay runner](../benchmarks/second_case_qualification_transfer.py)

## Discovery

The fit chooses one of four policies using the 70 existing discovery panels from 31 tasks, with all target tasks excluded. Each discovery cohort retains its original router budget. The bounded opening won. The two-pass rule exceeded the LMentry discovery budget by 32 lookups. [Frozen discovery fit](second-case-qualification-fit-v1.json)

| Policy | Discovery passes / lookups |
| --- | ---: |
| Bounded opening | 84,043 / 67,022 |
| Fixed switch | 84,020 / 67,921 |
| Fixed switch with two-pass gain | 83,925 / 67,963 |
| Fixed switch with every pass preserved | 83,982 / 67,920 |

## Target replay

Cells show final held-out passes and paid lookups. Both gates remain within the router's realized lookup budget in each of the seven target cohorts. The receipts include the matched-cost simple controls and verified native GEPA bounds for each guard.

| Cohort | Bounded opening | Fixed switch | Two-pass gain | Every pass preserved |
| --- | ---: | ---: | ---: | ---: |
| Bounded BBH | 6,347 / 13,421 | 6,327 / 13,551 | 6,345 / 13,536 | 6,325 / 13,546 |
| Bounded LMentry | 6,338 / 15,636 | 6,368 / 15,648 | 6,337 / 15,701 | 6,362 / 15,651 |
| Bounded MMLU | 7,719 / 6,554 | 7,724 / 6,634 | 7,719 / 6,647 | 7,724 / 6,636 |
| Four-case MMLU | 22,369 / 10,591 | 22,369 / 10,739 | 22,369 / 10,739 | 22,369 / 10,739 |
| Tie BBH | 2,145 / 12,521 | 2,146 / 12,588 | 2,145 / 12,558 | 2,145 / 12,588 |
| Tie LMentry | 992 / 6,971 | 995 / 6,996 | 995 / 6,998 | 995 / 6,997 |
| Additional MMLU | 7,398 / 6,354 | 7,398 / 6,485 | 7,398 / 6,485 | 7,398 / 6,485 |

On bounded BBH, the two-pass gate recovered 18 passes relative to the fixed switch, with a paired 95% range of 0 to +36. Only one of the 13 second-case nominees that cleared the ordinary gate was deployed on that arm's path. On bounded LMentry it deployed none of the five ordinary passes and lost 31 held-out passes against the fixed switch, with a range of −43 to −20.

Preserving every qualification pass kept 24 of the switch's 30 bounded LMentry gains over the bounded opening. On bounded BBH it scored two passes below the fixed switch. Across 2,048 archived episodes, the fixed switch promoted 24 second-case nominees. The two-pass arm promoted two of the 24 that would clear ordinary qualification on its own trajectories. The preservation arm promoted 20 of 24. The arm-specific counts include changes to later incumbents after a veto.

The two-pass arm matched the bounded opening's pooled pass count and used 616 more lookups. Preserving every pass added 10 pooled passes and used 594 more lookups. It exceeded the task-tuned native GEPA upper bound in four cohorts and tied in one at its realized spend. It exceeded the task-tuned simple point score only on bounded LMentry, with an inconclusive paired range. Pooled counts describe the archive because cohorts reuse tasks. The fit keeps the bounded opening. Fresh live superiority remains unverified.

## Reproduce offline

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Omit `--execute` and `--out` to preview a seal. [Benchmark requirements](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.second_case_qualification_transfer --fit \
  --execute 9eeefb9e7dc272eca96d927c30e73e71733ce058ce344adc1d0162e17171dc6b \
  --out NEW_FIT.json
PYTHONHASHSEED=0 python -B -m benchmarks.second_case_qualification_transfer \
  --cohort bounded-LMentry --fitted NEW_FIT.json \
  --execute 2b3ea2e7363ce987878e377c0bb0c293b72165a08cf05eae183bafe50a4352dd \
  --out NEW_REPORT.json
```

[Bounded BBH](second-case-qualification-transfer-bounded-bbh-v1.json) · [Bounded LMentry](second-case-qualification-transfer-bounded-lmentry-v1.json) · [Bounded MMLU](second-case-qualification-transfer-bounded-mmlu-v1.json) · [Four-case MMLU](second-case-qualification-transfer-four-case-mmlu-v1.json) · [Tie BBH](second-case-qualification-transfer-tie-bbh-v1.json) · [Tie LMentry](second-case-qualification-transfer-tie-lmentry-v1.json) · [Additional MMLU](second-case-qualification-transfer-additional-mmlu-v1.json)

Seventy-six targeted tests passed, including exhaustive checks over the binary qualification panels that start with an incumbent pass. Duplicate fits and all seven target replays matched byte for byte with DNS and outbound sockets blocked. The runner verified the qualification decisions against full independent panels and reproduced the bounded opening, fixed switch and router paths. It made zero provider requests. Storage Guard measured 9.7 GiB free. The source export, wheel overlay and publication checkout fit the standing 0.2 GiB LAB exception. [Tests](../tests/unit/test_second_case_qualification.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
