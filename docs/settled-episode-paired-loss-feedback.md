# Route rejected finalists using a paid paired loss

The qualification feedback policy saved 976 archived lookups with three fewer held-out passes than the packaged settled runner. Its trigger treated every rejected finalist the same. This study tests a distinction already available from the qualification receipt. A paired loss requires an observed incumbent pass and finalist fail for the same case and repeat. The other subtype means that the observed prefix contains no such pair. Early stopping can leave pairs unread. [Previous feedback result](settled-episode-qualification-feedback.md)

The fit starts with the frozen feedback actions for both rejection subtypes. It can change the follow-up action for one subtype while keeping the other fixed. A change needs support from at least three discovery subjects in the corresponding opening state. Both subtypes keep the original admission proof, and the finer routing buys no additional qualification reads. The fitter maximizes discovery passes at the prior feedback policy's realized lookup cap in each cohort and breaks ties by cost. [Benchmark](../benchmarks/settled_episode_paired_loss_feedback.py)

## Results

Of 39,365 distinct tables, 1,323 met the seven discovery lookup caps. The selected table keeps every original feedback action, with 84,078 discovery passes on 64,237 lookups. The witnessed-loss subtype had support from 8, 13, and 9 discovery subjects in the zero-, one-, and two-pass opening states. The other subtype had support from 21, 30, and 23 subjects.

Across 2,048 archived episodes, the selected table reproduced the original feedback result of 53,345 passes on 68,582 lookups. The paired differences from the earlier feedback scores were zero in all seven cohorts. These episode counts can repeat subjects across cohorts.

| Cohort | Rejection with an observed paired loss | Rejection with no paired loss observed |
| --- | ---: | ---: |
| Bounded BBH | 75 | 119 |
| Bounded LMentry | 61 | 107 |
| Bounded MMLU | 4 | 47 |
| Four-case MMLU | 2 | 40 |
| Tie BBH | 59 | 104 |
| Tie LMentry | 13 | 51 |
| Additional MMLU | 6 | 47 |
| **Total before a follow-up cycle** | **220** | **515** |

The current menu offers no better score-and-cost fit from changing either subtype at the frozen discovery budgets. The packaged feedback runner remains the candidate in the sealed live protocol. It exceeds the subject-tuned GEPA lookup-budget bound in the same three archived cohorts. Live superiority remains unverified. [Replay receipt](settled-episode-paired-loss-feedback-v1.json)

## Reproduce offline

Use the pinned GEPA 0.1.4 environment and a fresh receipt path.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.settled_episode_paired_loss_feedback --out /tmp/cpo-paired-loss.json
```

Two offline runs produced identical receipts. All 88 focused tests passed, including exact case and repeat pairing, handling of unread replies, and probe-cost and support checks. The prospective live plan reproduced byte for byte. Storage Guard measured 5.2 GiB free. The disposable source export, wheel overlay, and publication checkout fit the standing 0.2 GiB LAB exception and were removed. No provider requests were made. [Tests](../tests/unit/test_settled_episode_paired_loss_feedback.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
