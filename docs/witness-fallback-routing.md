# Route fallback using grades already paid for

Rules fitted on other benchmark families retained **274 of 306** added passes and saved **5,807 of 9,290** additional lookups against always running the eligible fallback. The transfer gate failed. The fit used a 50% training spending target, and three held-out families exceeded that target. The MMLU rule saved most of the calls and lost one pass against original CPO. [Sealed results](witness-fallback-routing-results-v1.json) · [MMLU result](prompteval-mmlu-witness-fallback.md) · [Bounded fallback](bounded-halving-fallback.md)

The study holds out BBH, LMentry, MMLU, and Promptolution one family at a time. It fits a single rule on the other families. The menu uses the observed incumbent pass fraction, the number of paid validation grades, and whether any observed challenger fixes an observed incumbent miss. These are the grades available at fallback entry. The incumbent pass fraction comes from adaptive witness reads. The fit chooses the highest mean gain across training tasks within half their unconditional fallback cost, with ties favoring cheaper rules. Each rule preserves the original 16-new-lookup cap and the unused independent admission.

The control routes by a fixed hash of each eligible episode's identity at rates of 10% through 90%, plus a zero-call option. The report includes the rate selected on training and the strongest blind point affordable at the measured held-out cost. Paired ranges against original CPO cluster repeats and model panels by physical case, then resample cases and subjects. The gate requires a positive lower endpoint, at most half the unconditional extra lookups, and at least the gain of the strongest affordable blind point on every held-out family.

| Held-out family | Rule fitted elsewhere | Unconditional added passes / lookups | Routed added passes / lookups | Affordable blind added passes / lookups | Paired 95% range vs. original CPO |
| --- | --- | ---: | ---: | ---: | ---: |
| BBH | Incumbent passes at most 30% of observed cases | 123 / 3,411 | 113 / 2,507 | 94 / 2,477 | +0.160 to +0.725 pp |
| LMentry | Incumbent passes at most 30% | 58 / 1,079 | 70 / 689 | 24 / 661 | +0.033 to +1.009 pp |
| MMLU | At least one paid paired win | 4 / 4,669 | −1 / 210 | 0 / 0 | −0.022 to +0.007 pp |
| Promptolution | Incumbent passes at most 30% | 121 / 131 | 92 / 77 | 70 / 72 | 0.000 to +3.819 pp |

The held-out budget drift blocks adoption. The paid rule beat the affordable blind point on BBH, LMentry, and Promptolution. It exceeded the spending target on each of those families. MMLU stayed within budget and underperformed retention. The result measures archived selection and lookup costs. The prospective model comparison still uses its sealed fixed policy. [Prospective comparison](grounded-witness-halving.md)

## Reproduce

Two socket- and DNS-blocked replays produced identical results. The unconditional replay matched the published cap‑16 gains and costs on all five task groups. Nine targeted tests passed, including a withheld-label test that changes a family's outcomes and verifies its fitted rule stays the same. Storage Guard measured 6.0 GiB free. The disposable source and wheel overlay fit within the standing LAB exception's 0.2 GiB scope. [Runner](../benchmarks/witness_fallback_routing.py) · [Tests](../tests/unit/test_witness_fallback_routing.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.promptolution_witness_capture --out PREDICTIONS.json
python -B -m benchmarks.witness_fallback_routing \
  --corpus PREDICTIONS.json \
  --execute 4a8a2c3189d567b34808ca78ebfd66428ef91cc62c041b99cd16f049308fc7fe \
  --out ROUTING.json
```
