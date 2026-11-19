# Fully funded validation of diagnostic hypotheses

A prior experiment offered 14 edits suggested by incompatible diagnostics. The search budget left every one without full validation. This follow-up gave a hinted edit and an unguided alternative the same validation allowance from the same search state. [Previous experiment](component-refresh.md)

## Protocol

Each trial reserved one complete 12-case validation panel beneath the 96- or 144-evaluation cap. A common CPO search used the remaining budget, and proposal votes required compatible training diagnostics. After search, the trial chose the highest-ranked validated parent that offered two eligible single edits. One edit came from an incompatible diagnostic. The alternative came from the remaining edit space. Both lacked compatible support and any previously measured validation rows. Ties used a hash of the seed and edit. When there was no pair, the two arms kept the common incumbent and left the reserve unspent.

For a matched pair, each arm ran a complete validation panel for its candidate. Promotion required a strict increase in exact validation passes and preservation of every critical validation pass from the incumbent. The experiment tested 48 new seeds across local, approval, known-routing, and unknown-routing profiles. The routing panels intentionally repeat cases with different dependency declarations. Holdout results were measured after selection. Costs include distinct evaluations and scripted proposal slots.

## Results

| Search policy | Held-out passes (of 13,824) | Search calls |
| --- | ---: | ---: |
| CPO reserve only | 9,448 | 36,009 |
| CPO funded diagnostic hint | 9,500 | 36,646 |
| CPO funded alternative | 9,448 | 36,646 |
| CPO dependency-aware, full search budget | 9,546 | 37,584 |
| CPO component-only, full search budget | 9,774 | 38,510 |
| GEPA dependency-aware, full search budget | 8,216 | 38,823 |

The trial found 49 pairs, including 28 at the incumbent. Hints earned 14 promotions and alternatives earned zero. The hinted arm gained 52 held-out passes at identical cost and preserved every matched critical pass against the alternative. It cleared that comparison in all six contextual panels. The local panels produced no eligible pairs. Full-budget dependency-aware CPO still gained 46 passes at a cost of 938 more calls.

Certified stopping replayed the same 49 hinted decisions using 354 candidate lookups instead of 588, a 40% reduction. The replay used cached incumbent measurements and counted only candidate lookups the certificate needed. The primary comparison charged all 588 lookups per arm.

The hinted arm beat both GEPA controls on the local panels and failed the critical-case gate on the contextual panels. GEPA 0.1.4 native merge terminated on seed `61275` in the three contextual profiles at both caps with the previously recorded all-zero ancestor weights error. Paired comparisons against that arm omit those six failures, and the affected panels cannot qualify. These findings come from deterministic cases with scripted proposals. The default CPO search policy remains unchanged. [Per-panel results](component-funded-exploration-results-v1.json)

## Reproduce

```sh
python -m pip install --require-hashes -r requirements-benchmark.txt
PYTHONHASHSEED=0 python -m benchmarks.component_funded_exploration
PYTHONHASHSEED=0 python -m benchmarks.component_funded_exploration --execute PLAN_SHA256 --out result.json
```

Use the seal from the preview command. Two runs with DNS and outbound sockets blocked produced byte-identical output.
