# Trace the affordable challengers missing from CPO’s final choice

The costed audit identified 85 losses where CPO could afford a full-panel path to GEPA’s score. Eighty required a single move from the start. Deferring deployment recovered six of those 85 losses and reduced aggregate accuracy. This audit traces every affordable single-move candidate through the original per-cycle CPO path. [Costed reachability](priced-gate-reachability.md) · [Deferred adoption](deferred-adoption.md)

For each losing comparison, the audit enumerates scheduled candidates that match the relevant GEPA holdout score and would pass both CPO gates against the original start. The complete validation and qualification panels must fit the measured episode spend. These hindsight targets are diagnostic. The original selector sees only its paid replies.

The audit intercepts original validation callbacks and verifies each cycle’s journal hash and total paid lookup count. It locates the furthest stage reached by any affordable single-move target. In order, the stages are earlier deployment, full scoring with another nominee, a paid pass on a known incumbent miss, other paid evidence, exclusion from the six-candidate wide roster, no paid reads, an archive move preempting fresh search, and failure to pass the actual cycle’s gates against its changed incumbent. The last category covers comparisons that required two moves even in hindsight. [Runner](../benchmarks/affordable_challenger_attribution.py)

## Results

Each row assigns a losing comparison to the furthest reached stage of any matching target. The same episode may contribute once against each GEPA control.

| Furthest stage on the measured CPO path | Llama and Mistral | Gemma and Flan | Total |
| --- | ---: | ---: | ---: |
| Deployed earlier | 3 | 1 | 4 |
| Fully scored, another nominee | 0 | 0 | 0 |
| Passed a known incumbent miss | 1 | 0 | 1 |
| Read without a paid gain witness | 36 | 14 | 50 |
| Outside the wide roster | 2 | 1 | 3 |
| Unread | 13 | 1 | 14 |
| Archive preempted fresh search | 4 | 2 | 6 |
| Blocked against the current incumbent | 2 | 0 | 2 |
| Required multiple moves | 2 | 3 | 5 |
| **Total** | **63** | **22** | **85** |

In 49 of the 50 read-without-witness comparisons, no matching target at that stage had more than one lookup. Only one of the 50 had a paid pass from any matching target at that stage. The largest group of losses therefore occurred before full validation of a matching challenger. The six-candidate limit was the furthest stage in three comparisons. No matching challenger was eliminated only after full scoring against another nominee. [Per-comparison ledgers and candidate stages](affordable-challenger-attribution-results-v1.json)

The audit uses held-out outcomes to identify viable targets after the fact. It establishes which stage blocked the observed choices. It leaves open whether a different first probe can reach those targets within the same lookup budget.

A follow-up alternated between two incumbent misses under bounded lookahead. It recovered two of the 50 read-without-witness comparisons and missed the overall lookup-savings gate. [Bounded miss alternation](bounded-miss-alternation.md)

## Reproduce

Use pinned GEPA 0.1.4 and a fresh output path. Two source-export runs matched byte for byte with sockets and DNS disabled and reproduced 84 published control traces. Five focused tests checked cached-read accounting, exact gate classification, full scoring, truncation, and archive preemption. The CLI rejected a stale seal and preserved an existing report. Storage Guard measured 12.8 GiB free. The 20.7 MB temporary overlay was removed under the standing LAB exception. [Tests](../tests/unit/test_affordable_challenger_attribution.py) · [Verification receipt](affordable-challenger-attribution-verification-v1.json) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.affordable_challenger_attribution \
  --execute ad0d26d01c0cc781a06be4ffa0c9e9f6a7bda40ef47d30e6f8fa6bb6763e1cff \
  --out NEW_REPORT.json
```
