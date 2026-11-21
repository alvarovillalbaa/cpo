# Fit first nominees to deployed prompt quality

The previous fit learned independent promotion outcomes. It changed many BBH and LMentry nominations and retained every MMLU nominee. This replay keeps the same paid validation features, search prefix, shortlist, and exact first proof. It tests whether labels based on the prompt actually deployed after that proof transfer better. [Qualification-trained comparison](witness-first-proof-fit.md) · [Runner](../benchmarks/witness_first_proof_gain.py)

For each already-paid candidate in development, run its exact proof. Measure the signed held-out difference between the prompt it would deploy and the original policy's deployed prompt. Also record the difference in paid proof lookups. Fit separate centered ridge models for the two differences, weighting episodes equally. A rejected proof is labeled with the retained incumbent's score and the actual reads it took. Each fit can read only development subjects from the other benchmark family.

The unguarded rule ranks by predicted gain. The primary rule also filters out candidates predicted to require more proof lookups than the original nominee. The original nominee remains eligible and wins ties. Both rules use paid validation to decide, submit one exact proof on the original independent cases, and keep the 24-lookup cap. The primary rule needs a positive paired lower endpoint against the original first proof in all three cohorts and must stay within seeded lookup spend. The lookup prediction filters candidates and the replay separately verifies actual cost.

## Results

| Cohort | Original passes / lookups | Qualification per lookup passes / lookups | Fitted gain passes / lookups | Fitted gain with cost guard passes / lookups |
| --- | ---: | ---: | ---: | ---: |
| BBH and LMentry | 17,068 / 71,071 | 17,215 / 71,233 | 17,072 / 71,137 | 17,074 / 71,091 |
| MMLU prior subjects | 21,180 / 34,122 | 21,180 / 34,122 | 21,180 / 34,122 | 21,180 / 34,122 |
| MMLU additional subjects | 8,976 / 13,639 | 8,976 / 13,639 | 8,976 / 13,639 | 8,976 / 13,639 |

On BBH and LMentry, the primary rule changed 13 nominees, gained six held-out passes, and used 20 additional lookups against the original first proof. The paired 95% interval was −0.073 to +0.104 percentage points. It scored 141 fewer passes and used 142 fewer lookups than the qualification-per-lookup fit. The paired interval against that fit was −0.874 to +0.178 points. The estimated cost filter saved 46 realized lookups relative to unguarded gain ranking. It still exceeded the original first proof by 20 lookups and stayed within the seeded control.

Both gain-trained rankers retained all 539 MMLU nominees. The two development fits observed 4,068 qualifying or retained deployments that scored above their originals on BBH and LMentry and 1,762 in MMLU. Fitting that downstream outcome left the MMLU decisions unchanged. The primary ranker missed the transfer gate. The comparison made zero provider requests. [Full outcomes, paired intervals, and fitted weights](witness-first-proof-gain-results-v1.json)

The follow-up changed the evidence gathered by witness search. It sought the second finalist on a different already-paid incumbent miss. [Split-finalist screen](witness-split-finalists.md)

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel from a clean source export. With sockets and DNS disabled, 57 targeted tests passed and two complete replays matched byte for byte. The published qualification-trained scores, costs, and paired intervals reproduced. The CLI rejected a stale seal, and the prospective live plan reproduced byte for byte. Storage Guard measured 6.4 GiB free. The export, wheel overlay, and publication worktree fit the standing 0.2 GiB LAB exception. [Split isolation and lookup guard tests](../tests/unit/test_witness_first_proof_gain.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.witness_first_proof_gain
python -B -m benchmarks.witness_first_proof_gain \
  --execute cf9f3daccc29be796274df81811ac244d57d5b8dc063b079c13dd130fdb47477 \
  --out NEW_REPORT.json
```
