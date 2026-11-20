# Trade one late challenger probe for an alternate miss

The bounded lookahead experiment found stronger candidates at higher cost. The cache-only experiment recovered none of the audited screening losses. This replay funds one new incumbent read by removing one challenger probe from the same deferred screen. [Bounded lookahead](bounded-miss-alternation.md) · [Cache-only follow-up](cached-miss-alternation.md)

The first four challengers receive the original probe. If all four fail and at least two challengers remain eligible to be screened, the method trades the last admitted challenger’s probe for one read of the next incumbent case after the routing and witness reads. If the incumbent misses it, the remaining challengers alternate between the two misses. Otherwise they continue using the original witness, with the same tail probe removed. The first passing challenger still requires the original exact gain certificate and separate qualification. If no challenger reaches proof, the method spends one incumbent read in place of one challenger read.

The routing branches, archive, original proof reserve, caps, and holdout stay fixed. The replay uses 28 archived Llama, Mistral, Gemma, and Flan panels. It verifies the original witness and official GEPA controls and retains the earlier 10% lookup savings and joint paired accuracy gate. [Runner](../benchmarks/late_miss_substitution.py)

## Results

Each cell gives final holdout passes and total paid search and qualification lookups.

| Method | Llama and Mistral | Gemma and Flan |
| --- | ---: | ---: |
| Original CPO route | 17,724 / 49,330 | 17,435 / 35,496 |
| Late miss substitution | 17,736 / 49,959 | 17,439 / 35,954 |
| Cache-only alternation | 17,719 / 50,369 | 17,440 / 36,047 |
| Earlier paid lookahead alternation | 17,732 / 52,150 | 17,459 / 37,785 |
| Batched GEPA, cap 52 | 17,694 / 57,271 | 17,422 / 40,184 |
| Sequential GEPA, cap 52 | 17,721 / 81,537 | 17,409 / 60,951 |

Late substitution gained 16 net holdout passes and used 1,087 more lookups than the original route. It made 2,156 substitutions, found 696 alternate misses, and produced 139 finalists from 2,399 alternate probes. It changed 50 final selections. The method recovered six of the 85 audited affordable-path losses, including four of the 50 that had stopped before observing a paid validation gain. [Panel totals and recoveries](late-miss-substitution-results-v1.json) · [Audited screening losses](affordable-challenger-attribution.md)

The method saved 12.8% and 10.5% against cap-52 batched GEPA. Its joint paired ranges against both cap-52 controls were −45 to +72 and −27 to +60. Both gates remain inconclusive. These two cohorts have already informed screen design, and the test uses fixed recorded prompt pools. CPO retains the original route.

A frozen transfer to 16 unused model and subject pairs missed the savings threshold and lost 12 passes against the original route. [Transfer results](late-miss-transfer.md)

## Reproduce

Use pinned GEPA 0.1.4 and a fresh output path. Two source-export runs matched byte for byte with sockets and DNS blocked and reproduced 140 published panel-control records. Three focused tests verified the tail substitution, alternate witness, and preserved early proof. The CLI rejected a stale seal and preserved an existing report. Storage Guard measured 11.7 GiB free. The 21.1 MB temporary overlay was removed under the standing LAB exception. [Tests](../tests/unit/test_late_miss_substitution.py) · [Verification receipt](late-miss-substitution-verification-v1.json) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.late_miss_substitution \
  --execute 0dbeaadd9b6581c6cf7683f6656c76c1ebabd4061c091278ffd2656165cde315 \
  --out NEW_REPORT.json
```
