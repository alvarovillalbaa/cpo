# Measure the headroom in the fixed AIME and ARC-AGI rosters

The joint search found stronger ARC-AGI nominees at additional cost and still trailed on AIME. This audit measures how much better a selector could do using the same candidate rosters and proof gates. It keeps the published case splits, starts, and lookup caps across all 1,520 trials. [Joint candidate race](recorded-joint-candidate-race.md) · [Audit runner](../benchmarks/recorded_math_roster_ceiling.py)

Each trial pays for the original incumbent qualification prefix and can retain the start. For every candidate, the audit finds the cheapest sufficient set of replies proving a strict qualification gain. It repeats the calculation with strict validation added, then with strict training on the same reserved half added. Validation also pays for the full incumbent score. For a paired proof, an incumbent failure or a challenger pass counts toward the exact lower bound. The audit credits already-paid observations and selects the cheapest remaining replies that can raise that bound above zero. [Observed incumbents and proof ordering](recorded-expected-training-order.md)

The audit sees every held-out grade and knows which replies will prove each candidate. It pays only for the selected candidate's sufficient evidence and pools the allowance across trials. A dynamic program finds the maximum held-out score at each published CPO budget, charging lookups and recorded ARC-AGI prices in separate runs. These optimistic ceilings bound the fixed replay. They do not estimate an attainable online policy or the benefit of generating new prompts.

| Archive and roster | Keep starts | Unrestricted roster | Strict qualification | Strict validation and qualification | All three strict gates |
| --- | ---: | ---: | ---: | ---: | ---: |
| AIME, original, four challengers | 500 | 589 | 535 | 509 | 501 |
| AIME, original, eight challengers | 500 | 606 | 548 | 512 | 503 |
| AIME, rotated, four challengers | 4,056 | 4,705 | 4,337 | 4,182 | 4,108 |
| AIME, rotated, eight challengers | 4,056 | 4,848 | 4,434 | 4,233 | 4,128 |
| ARC-AGI, original, four challengers | 575 | 1,636 | 1,636 | 1,636 | 1,636 |
| ARC-AGI, original, eight challengers | 575 | 1,679 | 1,679 | 1,679 | 1,679 |
| ARC-AGI, rotated, four challengers | 12,944 | 14,730 | 14,205 | 14,005 | 13,915 |
| ARC-AGI, rotated, eight challengers | 12,944 | 15,122 | 14,469 | 14,246 | 14,098 |

All three proof ceilings fit within each of the 24 published budgets under the optimistic accounting. Both CPO endpoints and the 12 distinct reported matched controls reproduced. The all-gates ceiling on eight-challenger rotated AIME was 4,128 using a minimum of 1,195 lookups. First-certificate CPO scored 4,082 on 8,191 lookups, and its best affordable GEPA control scored 4,080. Of the 46 passes between first-certificate CPO and the ceiling, 10 came from avoiding four harmful moves and 36 came from choosing a better admissible nominee in 18 trials. On the eight-challenger original AIME start, all-gates hindsight could gain at most three passes over keeping the start. [All budgets, proof floors, and decision attribution](recorded-math-roster-ceiling-results-v1.json)

On eight-challenger rotated ARC-AGI, the policy without training scored 13,932 on 8,239 lookups. Its gate-matched ceiling was 14,246 at a minimum of 3,614 lookups or $446.40 at recorded prices. Avoiding five harmful moves accounted for 10 passes of the 314-pass gap. Better eligible nominees accounted for the remaining 304 across 75 trials. The larger share of gate-matched headroom on both rotations is in choosing the prompt that reaches qualification. These are archived aggregate scores with repeated case identities across trials.

A follow-up located the missed nominees in the paid evidence and measured a four- or eight-read backup race. [Bounded backup experiment](recorded-bounded-certificate-backup.md)

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Two network-denied runs matched byte for byte. All 54 targeted tests passed from a clean export, including exhaustive check subsets and brute-force comparisons with the pooled cost frontier. The CLI rejected a stale seal. The public selector receipt and ordered live-plan preview reproduced. Storage Guard measured 2.9 GiB free. The export and publication worktree fit the standing 0.2 GiB LAB exception. No provider requests were sent.

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.recorded_math_roster_ceiling
python -B -m benchmarks.recorded_math_roster_ceiling \
  --execute a4d3db75e12dc59357c65d3ab00d2c56077444c6c2bef49b1cebe0623d99c41e \
  --out NEW_REPORT.json
```
