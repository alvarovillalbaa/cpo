# Give CPO and GEPA the same admission-attempt limit

CPO scored higher and used fewer lookups than both the cap-52 sequential and cap-80 batched GEPA controls on the 44 BBH and LMentry panels when all three methods could attempt admission once. PromptEval gave mixed results. [Full results](prompteval-matched-admission-attempt-results-v1.json)

This replay gives sequential GEPA, batched GEPA, and the rotating-witness CPO rule the option to end an episode after the first nominated prompt finishes independent admission. An unsuccessful nomination uses the attempt. Each method also has an unrestricted control that can try again in a later cycle. All arms keep their original selection rule, four-cycle proposal roster, episode-local search cache, and disjoint admission and final holdout cases. [Runner](../benchmarks/prompteval_matched_admission_attempt.py) · [Prior budget comparison](prompteval-witness-budget-controls.md)

The comparison uses the original 26 PromptEval panels and 44 archived BBH and LMentry panels on Airoboros 13B and Nous Hermes 13B. The additional panels use different tasks and models from the two PromptEval cohorts. They were captured for an earlier CPO study and played no part in choosing the one-attempt limit. The runner verifies the same physical held-out case IDs across both models for each subject. [Archive provenance](qualification-order-transfer.md)

The runner records the selected prompt and paid lookups when the first nominee finishes admission. Subsequent requests are outside that capped policy's budget. If no challenger is nominated, it charges the full search and retains the starting prompt. It verifies explicitly capped runs for the first seed of every panel and method. It also checks prior unrestricted counts and complete traces where settings recur, and reproduces the prior CPO one-attempt counts across all 26 PromptEval panels. GEPA retains its split-safe training and validation identities and full-round reserve.

| Archived cohort | CPO accuracy / lookups | Sequential GEPA, cap 52 | Batched GEPA, cap 80 |
| --- | ---: | ---: | ---: |
| Original nine PromptEval subjects | 48.054% / 30,914 | 47.915% / 26,244 | 47.989% / 37,903 |
| Four additional PromptEval subjects | 55.704% / 12,739 | 55.628% / 12,608 | 55.866% / 18,388 |
| BBH and LMentry, 22 tasks | 39.979% / 68,125 | 36.375% / 77,429 | 38.748% / 103,937 |

Each displayed arm has one attempt. Accuracy weights subjects equally. On BBH and LMentry, CPO gained 3.603 percentage points against the capped sequential control and 1.231 against the capped batched control, while using 12.0% and 34.5% fewer lookups respectively. Paired 95% ranges with subjects and cases resampled were +2.420 to +4.804 and +0.405 to +2.062 points. The batched comparison gained 99 pooled passes on BBH and 421 on LMentry.

On the additional PromptEval subjects, the capped sequential control used 131 fewer lookups than CPO. Its accuracy was 0.076 points lower, with a paired range crossing zero. The capped batched control gained 0.163 points and used 5,649 more lookups. On the original nine subjects, the capped sequential control was the best fixed native point within CPO's budget. On BBH and LMentry, every measured GEPA point cost more than capped CPO. The fixed native settings keep the full-round reserve and the same 24 validation anchors. Tighter native settings with a smaller validation panel remain outside this comparison.

On BBH and LMentry, unrestricted CPO scored 42.462% using 128,456 lookups. The admission limit cut 60,331 lookups and reduced score by 2.483 points. The evidence identifies a cheaper archived operating point and leaves fresh-model performance unverified.

A follow-up added nine native settings with fewer validation anchors. It found a batched GEPA setting within CPO's lookup budget and measured the accuracy gap with the comparator reselected in each paired draw. [Narrower native validation](prompteval-narrow-native-admission.md)

## Reproduce

Use Python 3.12 and hash-pinned GEPA 0.1.4. The full replay checked 350 explicit capped paths and reproduced the previously recorded unrestricted score, cost, and trace for 130 panel settings. A second clean source export reproduced the first and last panels in each of the three cohorts, including every measured arm. Verification blocked sockets and DNS. Storage Guard measured 6.2 GiB free. The task used temporary sources bounded at 0.2 GiB under the standing LAB exception and made zero provider requests. [Benchmark requirement](../requirements-benchmark.txt) · [Focused tests](../tests/unit/test_prompteval_matched_admission_attempt.py)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.prompteval_matched_admission_attempt
PYTHONHASHSEED=0 python -B -m benchmarks.prompteval_matched_admission_attempt \
  --execute aabf94577a04657b22de3e285196717ff165b9fc8af271e04400cf52459b9cd9 \
  --out NEW_REPORT.json
```

The results SHA-256 is `f0d3591f4d1eca35336ed1637a995894e44c2c5205eafa78b178ae306227efcf`.
