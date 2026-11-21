# Test whether one pre-proof read can reach an unopened candidate

The retry studies exercised candidates already reached by the original search. This comparison keeps the original search prefix and single independent proof, then lets one additional validation grade redirect that proof. The grade is bought only after search nominates a prompt. A qualifying probe case is a paid miss for that nominee on its own validation panel. A case the incumbent also missed takes precedence. [MMLU gap audit](witness-mmlu-gap.md) · [Runner](../benchmarks/witness_unread_nominee_probe.py)

The unread arm offers the first unopened alternative from the nominee's cycle. The paid arm offers the highest smoothed validation scorer with a missing grade on the probe case. It uses the same case preference and buys one missing grade. A pass sends the alternative to the original independent proof. A fail sends the original nominee. The proof inherits the same assigned rows and tie extension and loses one of its 24 reads whenever a probe runs. Every candidate already exists in the archived roster, so the comparison prices the grade and proof on those supplied prompts.

The retrospective audit counts whether any enrolled prompt beat both the original nominee and the start on held-out cases. It records whether at least one such prompt was paid, unread, or unread in the nominee's own cycle. These categories can overlap. For episodes without a nominee, the comparison floor is the start. The audit runs after the policies have committed their decisions. The held-out grades are unavailable to the probe.

## Results

| Cohort | Full single proof passes / lookups | Unread probe passes / lookups | Paid probe passes / lookups | Unread probe attempts / redirects |
| --- | ---: | ---: | ---: | ---: |
| BBH and LMentry | 17,068 / 71,071 | 17,090 / 71,353 | 17,079 / 71,417 | 295 / 33 |
| MMLU prior subjects | 21,180 / 34,122 | 21,184 / 34,170 | 21,180 / 34,172 | 75 / 3 |
| MMLU additional subjects | 8,976 / 13,639 | 8,978 / 13,682 | 8,972 / 13,678 | 49 / 1 |

Of 539 MMLU episodes with a nominee, 375 had an unread alternative that scored above both current prompts. In 184 of those episodes, at least one such alternative belonged to the nominee's cycle. The one-read rule redirected only four MMLU nominations and gained six pooled passes at 91 additional lookups. Its paired intervals against the full single proof included zero in both cohorts. MMLU training selected the unread probe for BBH and LMentry. The other direction selected the paid probe for MMLU. Neither direction passed the transfer gate. [Costs, selected rules, and paired intervals](witness-unread-nominee-probe-results-v1.json)

Of the 293 MMLU episodes with no nominee, 280 had a stronger candidate with at least one paid grade. No episode in that group had a stronger unread candidate. This points to a gap in the evidence used to nominate among candidates the search already reached. The counts measure held-out quality before pricing a new independent proof. [Coverage counts by cohort](witness-unread-nominee-probe-results-v1.json)

Pricing all paid candidates found an independently qualifying improvement in 205 of those episodes. The four paid-evidence selectors failed the transfer gate. [No-nominee admission replay](witness-no-nominee-admission.md)

## Reproduce

Use a clean source export with Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. With sockets and DNS blocked, 41 targeted tests passed and two replays matched byte for byte. The original single-proof scores and costs reproduced. The CLI rejected a stale seal and the prospective live plan reproduced byte for byte. Storage Guard measured 5.2 GiB free. The export, overlay, and publication worktree fit the standing 0.2 GiB LAB exception. [Probe tests](../tests/unit/test_witness_unread_nominee_probe.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.witness_unread_nominee_probe
python -B -m benchmarks.witness_unread_nominee_probe \
  --execute 6bb0c10be6cd7c48560055823c0bfefa6d0fe8db49af2f9fe7b81bd04ae32e1a \
  --out NEW_REPORT.json
```
