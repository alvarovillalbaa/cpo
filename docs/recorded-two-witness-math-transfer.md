# Test the public two-witness selector on archived AIME and ARC-AGI

This replay applies the frozen public selector to the recorded AIME and ARC-AGI prompt pools. It uses the original and rotated starting prompts, four- and eight-challenger rosters, and the same seeded training, validation, qualification, and holdout splits. The selector retains exact validation and the original strict training and qualification proofs. First-certificate CPO, qualification-first CPO, and both original-cap GEPA traces reproduced on all 1,520 trials before comparison. [Public selector](two-witness-pool.md) · [Math splits and original controls](recorded-first-training-certificate.md)

Both GEPA 0.1.4 modes sweep every integer search cap from the validation width through 180. Search and qualification both count toward the realized lookup budget. ARC-AGI also has recorded evaluator prices, which the replay uses for a separate historical-cost comparison. In each paired draw, all trials sharing a held-out case move together. The draw selects the strongest affordable fixed GEPA setting or the zero-cost retained start. [Runner](../benchmarks/recorded_two_witness_math_transfer.py) · [All settings and prices](recorded-two-witness-math-transfer-results-v1.json)

| Archive and starting prompts | CPO passes / lookups | Best affordable comparator passes / lookups | Margin and paired 95% range |
| --- | ---: | ---: | ---: |
| AIME, original, four challengers | 491 / 976 | 500 / 0 | −9, −25 to +1 |
| AIME, original, eight challengers | 487 / 1,174 | 500 / 0 | −13, −32 to −5 |
| AIME, rotated, four challengers | 4,063 / 7,205 | 4,080 / 6,630 | −17, −49 to +4 |
| AIME, rotated, eight challengers | 4,056 / 8,744 | 4,080 / 6,630 | −24, −60 to −5 |
| ARC-AGI, original, four challengers | 1,544 / 1,769 | 1,565 / 1,472 | −21, −42 to −2 |
| ARC-AGI, original, eight challengers | 1,547 / 1,937 | 1,568 / 1,928 | −21, −40 to −5 |
| ARC-AGI, rotated, four challengers | 13,723 / 8,149 | 13,757 / 7,683 | −34, −72 to +3 |
| ARC-AGI, rotated, eight challengers | 13,738 / 9,264 | 13,775 / 9,137 | −37, −74 to +1 |

On the AIME eight-challenger rotation, keeping every start matched the public selector's 4,056 passes without evaluations. Sequential GEPA at cap 24 scored 4,080 with 6,630 lookups. The earlier first-certificate CPO scored 4,082 at 8,191 lookups, with a paired range of −33 to +23 against the affordable frontier.

On the ARC-AGI eight-challenger rotation, sequential GEPA at cap 40 scored 37 more passes and used 127 fewer lookups than the public selector. Its historical evaluation cost was $1,160.72 versus $1,219.22 for CPO. The same control won under both budget measures. On the original ARC start with eight challengers, changing from lookup to historical-cost matching selected a different control and still favored GEPA. Qualification-first CPO remained the strongest tested CPO policy on the rotated eight-challenger ARC setting. Its historical-cost matched margin was +38, with a range of −13 to +86. These comparisons use recorded outcomes for fixed prompt pools.

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. With DNS and socket connections blocked, 77 targeted tests and five subtests passed. Two full replays matched byte for byte. Direct replay verified 12 reported GEPA settings across 2,600 trials. The original selector parity receipt and live-plan preview reproduced. The CLI rejected a stale seal. Storage Guard measured 4.6 GiB free. The export and publication worktree fit the standing 0.2 GiB LAB exception. The replay sent zero provider requests.

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.recorded_two_witness_math_transfer
python -B -m benchmarks.recorded_two_witness_math_transfer \
  --execute 0be80405d9e5e32d3a453f02913de3f4a7ae588243aa73b16456e73bac4d1fd8 \
  --out NEW_REPORT.json
```
