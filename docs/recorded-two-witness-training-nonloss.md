# Allow exact training ties in the two-witness policy

The original MMLU replay found little usable headroom when a challenger had to improve on validation, training, and qualification. This replay changes the training threshold from a gain of one pass to a gain of zero. It keeps the same public two-witness selector, training reserve, strict validation and qualification gains, and proof order. The earlier 14-subject cohort provides the comparison with the published strict policy. Five additional subjects on Gemma 7B base and Flan-T5 XXL provide task and checkpoint transfer. World religions appeared in the earlier certificate studies and was excluded by task identity before replay. [Prior MMLU replay](recorded-two-witness-mmlu-transfer.md) · [Additional archive](posterior-model-transfer.md)

The check covers the first half of the ten training cases. A certified tie can restore the same qualified nominee that the strict training check vetoed. The replay verified identical nominations, qualification lookup counts, and non-training search lookup counts on all 1,216 paired trials. Each restored prompt tied the incumbent on the complete training half. [Runner](../benchmarks/recorded_two_witness_training_nonloss.py) · [Full results](recorded-two-witness-training-nonloss-results-v1.json)

| MMLU cohort | Strict passes / lookups | Nonloss passes / lookups | Restored deployments | Nonloss margin over strict and paired 95% range |
| --- | ---: | ---: | ---: | ---: |
| Earlier cohort, 14 subjects | 26,628 / 18,165 | 26,637 / 18,179 | 33 | +9, −15 to +34 |
| Disjoint cohort, five subjects | 15,042 / 5,645 | 15,041 / 5,644 | 12 | −1, −23 to +21 |

The earlier cohort had 34 gross gained passes and 25 gross lost passes from the restored deployments. Retaining the starts scored 26,625 at zero lookups and remained the best affordable comparator. The paired margin for nonloss versus the best affordable setting was +12, with a range of −20 to +36.

The disjoint cohort had 12 gross gained passes and 13 gross lost passes. Retaining the starts matched the nonloss score at zero lookups. Sequential GEPA at cap 16 scored 15,047 with 3,223 lookups, six more passes and 2,421 fewer lookups than nonloss. The paired nonloss margin against the reselected affordable GEPA setting ranged from −31 to +17. Training ties increased the number of deployable prompts in both cohorts and did not establish a reliable improvement.

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. With sockets and DNS blocked, 75 targeted tests and five subtests passed and two full replays matched byte for byte. The strict shortlist paths and all earlier GEPA frontier costs and scores reproduced. The original public selector parity receipt and live-plan preview still matched. The CLI rejected a stale seal. Storage Guard measured 4.7 GiB free. The export and publication worktree fit the standing 0.2 GiB LAB exception. The replay sent zero provider requests.

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.recorded_two_witness_training_nonloss
python -B -m benchmarks.recorded_two_witness_training_nonloss \
  --execute 98b98e215bdec5ee0ea618ff9f3446b6fbfd530cf30b5d6360dcc3049daefaab \
  --out NEW_REPORT.json
```
