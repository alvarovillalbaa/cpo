# Check the sibling after a full validation rejection

Comparing both openings directly changed which candidate advanced and lowered holdout accuracy. This replay retains the earlier eight-case screen with zero later proposer calls. If the screen picks a finalist that fails full validation, CPO can use its remaining budget to test the other supplied opening. Successful original nominations follow their original path. [Opening-pair replay](proposal-opening-pool.md) · [Runner](../benchmarks/proposal_opening_rescue.py)

The incumbent and rejected finalist already have all 24 validation replies. The rescue reuses them and spends at most 24 more lookups on the sibling. The exact pooled evaluator can reject a sibling early. **Screened rescue** first requires the sibling to at least tie the incumbent on the original eight-case prefix. Both arms keep the 72-lookup search ceiling. A rescued challenger must beat the incumbent on full validation before it can enter the original independent qualification.

The primary comparison uses the unscreened rescue on the eight additional Gemma and Falcon panels. The gate requires a positive joint paired 95% range against both GEPA modes at or below both control lookup totals. [Archive provenance](independent-mmlu-transfer.md)

## Results

| Method | Development passes / lookups | Earlier transfer passes / lookups | Additional archive passes / lookups |
| --- | ---: | ---: | ---: |
| Original cap-72 CPO | 4,159 / 33,177 | 10,237 / 66,831 | 9,000 / 66,958 |
| Eight-case screen, zero later callbacks | 4,158 / 20,860 | 10,247 / 42,220 | 9,023 / 43,175 |
| Rescue | 4,165 / 22,925 | 10,228 / 46,097 | 9,017 / 47,604 |
| Screened rescue | 4,165 / 22,900 | 10,228 / 46,118 | 9,017 / 47,502 |
| Sequential GEPA | 4,139 / 44,944 | 10,236 / 91,649 | 9,012 / 92,773 |
| Batched GEPA | 4,176 / 44,194 | 10,263 / 88,226 | 9,020 / 89,426 |

On the additional archive, Rescue opened 309 sibling challenges across 1,024 cycles and nominated 53 finalists. It scored six fewer holdout passes and spent 4,429 more lookups than the unmodified eight-case screen. Against batched GEPA it finished three passes behind and used 41,822 fewer lookups. The joint paired 95% range was −52 to +37 passes, so it missed the gate. The prefix check screened out 64 challenges, saved 102 lookups against Rescue, and reached the same aggregate holdout score.

Rescue improved the development score by seven passes. It lost 19 on the earlier transfer archive while adding 3,877 lookups. The earlier eight-case screen scored higher at lower cost on both transfer cohorts. CPO’s default search stays in place. [Panel outcomes, rescue counters, and intervals](proposal-opening-rescue-results-v1.json)

## Reproduce offline

Use pinned GEPA 0.1.4 and a fresh output path.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.proposal_opening_rescue
PYTHONHASHSEED=0 python -B -m benchmarks.proposal_opening_rescue \
  --execute 1429cb2d29a181313aac4eafa5aa64edcc7d582cfb22d7e81c101dcbe6d63232 \
  --out NEW_REPORT.json
```

Two clean source replays blocked sockets and DNS and matched byte for byte. Each exercised 5,120 experimental cycles and reproduced 100 published panel traces. Seven focused tests passed, including successful-original preservation, sibling qualification, and the funding bound. The runner rejected a stale seal and preserved an existing report. Storage Guard measured 4.2 GiB free. The 27.1 MB scratch export was removed under the standing LAB exception. [Tests](../tests/unit/test_proposal_opening_rescue.py) · [Verification receipt](proposal-opening-rescue-verification-v1.json) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
