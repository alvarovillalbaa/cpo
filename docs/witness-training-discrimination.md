# Keep the training examples that expose policy errors

The completed Luna v1 search journal shows that the shared two-example opening included only two of six available ticket queue labels. Warehouse and outage each included four of five available categorical field values. The audit verified the archived task documents against the live plan before counting the string and boolean values in the saved opening requests. This establishes the examples the proposer received. The trial did not isolate their effect on model accuracy. [First live result](model-backed-validation.md#first-live-result)

The new replay uses the separate grounded witness benchmark's 16-example blocks. It keeps the smallest subset that preserves every categorical field value and every named policy error the full block exposes. Exact subset search breaks ties by the original row order. The competing rules include wrong queue mappings, stock and inspection errors, and credit and review boundary errors. The selector reads training labels. The scorer then checks which unresolved rules would fail on the fixed development and confirmation cases. [Regime coverage](grounded-witness-regime-coverage.md) · [Replay runner](../benchmarks/witness_training_discrimination.py)

## Results

| Task | Examples per block, full → selected | Policy errors distinguished per block | Equal-size prefixes with unresolved scoring errors |
| --- | ---: | ---: | ---: |
| Ticket | 16 → 8 | 8 | 0 of 4 |
| Warehouse | 16 → 8 | 17 | 4 of 4 |
| Outage | 16 → 4 | 10 | 4 of 4 |

The exact cover retained all training labels and policy distinctions across 12 blocks. It reduced the examples from 192 to 80 and serialized reflection input from 37,602 to 16,566 bytes, a **55.9% reduction**. At the same size, the warehouse prefix omitted both `RELEASE` and `REVIEW` in one block. Every outage prefix left the 30-minute exclusion error undetectable. Two development cases and one confirmation case distinguish that error. The byte counts describe serialized inputs. Proposal quality, provider token counts, and CPO's live advantage over GEPA remain unverified. [Full receipt and per-cycle cases](witness-training-discrimination-results-v1.json)

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. With sockets and DNS blocked, 36 targeted tests passed and two complete replays matched byte for byte. The CLI rejected a stale seal, and the prospective live-plan preview reproduced byte for byte. Storage Guard measured 6.2 GiB free. The 39 MiB export and bounded publication worktree used the standing 0.2 GiB LAB exception. The replay made zero provider requests. [Coverage and isolation tests](../tests/unit/test_witness_training_discrimination.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.witness_training_discrimination
python -B -m benchmarks.witness_training_discrimination \
  --execute 48acf0d58b6eb0e6541cdda257448b1c8c9157a8b81fae77b7b9077e07915a66 \
  --out NEW_REPORT.json
```
