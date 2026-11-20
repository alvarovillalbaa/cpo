# Compare both supplied opening proposals

The eight-case screen with zero later proposer calls saved substantially on evaluation lookups. Its search could leave the second opening unused after an improvement on the first. This replay compares the two supplied proposals directly within a 72-lookup ceiling. The finalist progresses to independent qualification only if it earns a strictly higher total score across all 24 validation cases. [Reflection cap replay](proposal-reflection-cap.md) · [Runner](../benchmarks/proposal_opening_pool.py)

**Screened pair** scores both proposals and the incumbent on the first eight seeded validation cases. It admits any proposal with a strict gain on that prefix and selects the highest exact score among the admitted proposals and incumbent. **Screen then fallback** checks admitted proposals in prefix score order and keeps the first strict full-panel improvement. **Full pair** admits both proposals without screening. All three use the existing pool evaluator’s exact rejection bound, reuse paid replies, and make zero later proposer calls. The maximum search cost is 24 cases for each of three prompts.

The primary arm is Screened pair on the eight additional Gemma and Falcon panels. Its gate requires a positive joint paired 95% range against both GEPA modes and paid lookups at or below both controls. [Archive provenance](independent-mmlu-transfer.md)

## Results

| Method | Development passes / lookups | Earlier transfer passes / lookups | Additional archive passes / lookups |
| --- | ---: | ---: | ---: |
| Original cap-72 CPO | 4,159 / 33,177 | 10,237 / 66,831 | 9,000 / 66,958 |
| Earlier eight-case screen, zero later callbacks | 4,158 / 20,860 | 10,247 / 42,220 | 9,023 / 43,175 |
| Screened pair | 4,165 / 19,317 | 10,217 / 39,762 | 8,996 / 40,756 |
| Screen then fallback | 4,164 / 19,023 | 10,220 / 39,202 | 8,999 / 39,727 |
| Full pair | 4,171 / 30,339 | 10,199 / 62,246 | 9,012 / 64,051 |
| Sequential GEPA | 4,139 / 44,944 | 10,236 / 91,649 | 9,012 / 92,773 |
| Batched GEPA | 4,176 / 44,194 | 10,263 / 88,226 | 9,020 / 89,426 |

On the additional archive, both proposals advanced past the prefix in 153 of 1,024 cycles in the primary arm. Screened pair used 2,419 fewer lookups and scored 27 fewer passes than the earlier zero-later-call screen. Against batched GEPA it used 48,670 fewer lookups and scored 24 fewer passes. The joint paired 95% range was −72 to +10 passes.

Full pair gained 16 passes over Screened pair on the additional archive and spent 23,295 more lookups. On earlier transfer it fell 64 passes behind batched GEPA, with a joint paired range of −118 to −15. The earlier eight-case screen with zero later callbacks had the highest holdout score among the opening-only methods on both transfer cohorts. The results leave the original search in place. [Panel scores, paid costs, and paired ranges](proposal-opening-pool-results-v1.json)

## Reproduce offline

Use pinned GEPA 0.1.4 and a fresh output path.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.proposal_opening_pool
PYTHONHASHSEED=0 python -B -m benchmarks.proposal_opening_pool \
  --execute d34efbed1b1a25694134b1c7e066b472df98146184043f9aaff27b92db1a2bfe \
  --out NEW_REPORT.json
```

Two clean source replays blocked sockets and DNS and matched byte for byte. Each exercised 7,680 experimental cycles and reproduced 100 published panel traces. Six focused tests passed, including second-proposal fallback, full validation ranking, and the funding bound. The runner rejected a stale seal and preserved an existing report. Storage Guard measured 6.0 GiB free. The 27.0 MB scratch export was removed under the standing LAB exception. [Tests](../tests/unit/test_proposal_opening_pool.py) · [Verification receipt](proposal-opening-pool-verification-v1.json) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
