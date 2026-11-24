# Measure what paid evidence can tell CPO about a second-case promotion

The [qualification study](second-case-qualification-transfer.md) found that a two-pass requirement recovered much of the case switch's bounded BBH loss and erased its bounded LMentry gain. This audit asks whether a veto based on already-paid evidence can improve the choice. For the first ordinarily qualified second-case nominee in each episode, it compares deploying the nominee with retaining the incumbent. Both paths continue with the same fixed switch for their remaining cycles. Each episode allows one veto, and it occurs after the original qualification has cleared. Both arms keep all lookups paid up to that decision. [Replay and fitter](../benchmarks/second_case_evidence_transfer.py)

The **paid summary** uses the exact lower bound on qualification gain and counts of observed paired repairs and losses. The **paid transcript** uses the ordered validation and qualification replies, with prompt names and case IDs replaced by roster and panel positions. Each veto rule requires support from at least two distinct discovery tasks and a positive total discovery pass gain for vetoing that evidence class. New and unsupported classes keep the nominee. A separate hindsight calculation can distinguish all paired qualification differences after the entire panel is read. This third calculation is diagnostic and buys no extra replies in the evaluated policies.

## Discovery

The 70 discovery panels from 31 tasks exclude all target tasks. Across them, 28 episodes contain an eligible promotion. Eight promotions reduce final held-out passes, 16 increase them, and four leave the count unchanged. Every event maps to one of two paid summary classes. Both classes mix helpful and harmful promotions, and neither has a positive aggregate veto gain.

| Policy | Discovery passes / lookups | Vetoes |
| --- | ---: | ---: |
| Bounded opening | 84,043 / 67,022 | — |
| Fixed switch, keep every promotion | 84,020 / 67,921 | 0 |
| Paid summary rule | 84,020 / 67,921 | 0 |
| Paid transcript rule | 84,028 / 67,910 | 4 |
| Veto every first promotion | 83,936 / 67,957 | 28 |

The transcript rule finds 24 classes, with four supported by multiple tasks and two chosen for veto. The original cohort budgets allow both evidence rules. The bounded opening wins. Even perfect hindsight over the 28 first opportunities can recover only 20 passes, for 84,040 total. That falls three passes below the bounded opening before applying lookup caps. The best common transcript rule in hindsight recovers 17, and adding complete paired qualification differences leaves that ceiling at 17. [Frozen fit and class counts](second-case-evidence-fit-v1.json)

## Target replay

The replay reproduces every paid path of the fixed switch. There are 24 first eligible promotions across 2,048 archived target episodes. Nine hurt final scores, 11 help, and four leave the score unchanged. The paid transcript has discovery support for four target events and vetoes three. The paid summary keeps every promotion.

| Cohort | Opportunities | Fixed switch passes / lookups | Transcript passes / lookups | Transcript vetoes | Best event-specific veto gain in hindsight |
| --- | ---: | ---: | ---: | ---: | ---: |
| Bounded BBH | 13 | 6,327 / 13,551 | 6,331 / 13,543 | 1 | +27 |
| Bounded LMentry | 5 | 6,368 / 15,648 | 6,366 / 15,645 | 1 | 0 |
| Bounded MMLU | 2 | 7,724 / 6,634 | 7,719 / 6,634 | 1 | 0 |
| Four-case MMLU | 0 | 22,369 / 10,739 | 22,369 / 10,739 | 0 | 0 |
| Tie BBH | 3 | 2,146 / 12,588 | 2,146 / 12,588 | 0 | 0 |
| Tie LMentry | 1 | 995 / 6,996 | 995 / 6,996 | 0 | 0 |
| Additional MMLU | 0 | 7,398 / 6,485 | 7,398 / 6,485 | 0 | 0 |

The frozen transcript rule lost three passes and saved 11 lookups versus the fixed switch across the archive. Vetoing all 24 lost 30 passes and saved 13 lookups. A single task-blind rule chosen after seeing all target outcomes could recover 20 passes with the 18 transcript classes. Refining those classes by the complete paired qualification differences produces 19 classes and the same 20-pass ceiling. Both refinements still have two classes that mix helpful and harmful promotions. The 27-pass event-specific ceiling is specific to the first eligible promotion on these archived paths. The hindsight calculations ignore lookup caps. Pooled figures describe the archive because cohorts reuse tasks.

At the transcript rule's actual spend, it exceeded the task-tuned native GEPA upper bound in four cohorts and tied in one. The task-tuned simple point score remained higher in six cohorts. The one-veto design has too little discovery headroom to beat the bounded opening, and richer summaries of the same four qualification cases offer limited additional discrimination in this replay. The bounded opening remains the fitted choice. Fresh live superiority remains unverified.

## Reproduce offline

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Omit `--execute` and `--out` to preview a seal. [Benchmark requirements](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.second_case_evidence_transfer --fit \
  --execute 0e2b983fadceb213066587d35fa35ceeb44bfe9ae67930ba17b20501262386ce \
  --out NEW_FIT.json
PYTHONHASHSEED=0 python -B -m benchmarks.second_case_evidence_transfer \
  --cohort bounded-BBH --fitted NEW_FIT.json \
  --execute 59eb60c11fcb05df3d6c2ecdf0cd249821a32cae188a2dd5c9315e54333196e7 \
  --out NEW_REPORT.json
```

[Bounded BBH](second-case-evidence-transfer-bounded-bbh-v1.json) · [Bounded LMentry](second-case-evidence-transfer-bounded-lmentry-v1.json) · [Bounded MMLU](second-case-evidence-transfer-bounded-mmlu-v1.json) · [Four-case MMLU](second-case-evidence-transfer-four-case-mmlu-v1.json) · [Tie BBH](second-case-evidence-transfer-tie-bbh-v1.json) · [Tie LMentry](second-case-evidence-transfer-tie-lmentry-v1.json) · [Additional MMLU](second-case-evidence-transfer-additional-mmlu-v1.json)

Seventy-nine targeted tests passed. Duplicate fits and target replays matched byte for byte with DNS and outbound sockets blocked. The audit checked source hashes, original trajectory hashes, paired case totals and affordable native anchors. It made zero provider requests. Storage Guard measured 9.7 GiB free. The source export, GEPA overlay and publication checkout fit the standing 0.2 GiB LAB exception. [Tests](../tests/unit/test_second_case_evidence_transfer.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
