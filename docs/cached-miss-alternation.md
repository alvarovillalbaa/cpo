# Diversify first probes using earlier paid misses

Bounded miss alternation improved held-out scores on two cohorts and fell short of the lookup savings requirement. Its matched scan showed that seeking a second miss accounted for 2,173 additional lookups with every deployment unchanged. This replay uses an alternate only when the answer to it is already in the episode’s validation cache. [Paid lookahead experiment](bounded-miss-alternation.md)

The first challenger keeps the original probe. Later challengers alternate between that probe and a different case on the current validation panel where the same incumbent failed in an earlier cycle. The selector prefers a cached miss that another prompt previously answered correctly. Ties follow the scheduled case order. If the cache supplies no distinct miss, it keeps the original shared probe. The alternate costs no additional incumbent lookahead. A challenger that passes still needs a strict validation certificate and independent paired qualification.

Only the deferred first-gain branch changes. The replay captures the validation cache before each fresh search and verifies its lookup count. Its capture-only control must reproduce all original traces, costs, and deployments. Both methods retain the same proposal pools, archive, search cap, and independent qualification. The 28 archived panels and GEPA controls match the bounded lookahead experiment. [Runner](../benchmarks/cached_miss_alternation.py)

## Results

Each cell gives final holdout passes and paid search plus qualification lookups.

| Method | Llama and Mistral | Gemma and Flan |
| --- | ---: | ---: |
| Original CPO route and cache-observed control | 17,724 / 49,330 | 17,435 / 35,496 |
| Cached alternation | 17,719 / 50,369 | 17,440 / 36,047 |
| Paid lookahead alternation | 17,732 / 52,150 | 17,459 / 37,785 |
| Batched GEPA, cap 52 | 17,694 / 57,271 | 17,422 / 40,184 |
| Sequential GEPA, cap 52 | 17,721 / 81,537 | 17,409 / 60,951 |

Cached alternation changed 44 final prompts and tied the original route’s pooled score with 1,590 additional lookups. It recovered none of the 85 audited affordable-path losses. The cache offered a distinct alternate in 666 deferred cycles, producing 153 finalists from 2,636 alternate probes. Although witness discovery was free, the changed trajectories spent more on search and qualification. A retrospective check of the original paths found that 14 of the 50 screening losses had an eligible alternate for at least one matching challenger in a roster position where the policy would use it. The ranked alternate was a passing probe for five of those comparisons in the full archive. Those are probe opportunities, and nominations still depend on earlier contenders and exact validation. [Panel totals and paired ranges](cached-miss-alternation-results-v1.json) · [Audited targets](affordable-challenger-attribution-results-v1.json)

Cached alternation saved 12.1% and 10.3% against cap-52 batched GEPA. Its joint paired accuracy ranges against both cap-52 GEPA modes were −61 to +54 and −33 to +67. Both gates remained inconclusive. The original screen stays in place. The comparison uses recorded prompt pools, with fresh-model performance still open.

## Reproduce

Use pinned GEPA 0.1.4 and a fresh output path. Two source-export replays matched byte for byte with sockets and DNS blocked. They reproduced 140 published panel-control records, and the cache-observed arm matched the original callback trace on every panel. Three focused tests verified witness priority, the original fall-through, and absence of paid incumbent lookahead. The CLI rejected a stale seal and preserved an existing report. Storage Guard measured 12.3 GiB free. The 21.0 MB temporary overlay was removed under the standing LAB exception. [Tests](../tests/unit/test_cached_miss_alternation.py) · [Verification receipt](cached-miss-alternation-verification-v1.json) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.cached_miss_alternation \
  --execute 164d9cdf62ef7432ad787db53d63739a9e2af08cd9557d63666a717e782cba8e \
  --out NEW_REPORT.json
```
