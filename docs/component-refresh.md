# Refreshing feedback after a dependency changes

An earlier study found that dependency checks prevent stale diagnostic transfer, but can remove useful edit suggestions. This follow-up tested remeasuring the original training case and offering the suggested edit for fresh validation. Both variants used only compatible diagnostics for proposal votes. [Earlier comparison](component-dependencies.md)

## Design

The study used 16 new seeds, evaluation caps of 96 and 144, and the same four deterministic profiles as the dependency study. Across panels, each arm was scored on 4,608 held-out cases. The known and unknown routing panels share cases to isolate the dependency declaration. Search used only training and validation rows. Costs include distinct evaluations and scripted proposal slots.

- **Refresh** replaces the last scheduled training probe with an unmeasured case whose earlier diagnostic depends on changed context. It skips rechecks when the case is already scheduled. The matched control probes an unmeasured case in the same task family with the same critical status. Both require a matching row before replacing a probe.
- **Explore** gives the second proposal slot to an unsupported edit suggested by an incompatible diagnostic. The matched control offers a different unsupported edit whenever the same kind of choice exists. Both use fresh validation and the same round cap.
- **Reference arms** use ordinary CPO with dependency-aware or component-only reuse. Official GEPA 0.1.4 uses the same dependency-aware proposer with and without its native merge operator.

## Results

| Search and reuse policy | Held-out passes | Search calls | Stale diagnostic admissions |
| --- | ---: | ---: | ---: |
| CPO dependencies | 3,407 | 12,558 | 0 |
| CPO component only | 3,671 | 13,006 | 300 |
| CPO refresh | 3,387 | 12,605 | 0 |
| CPO matched refresh | 3,411 | 12,569 | 0 |
| CPO explore | 3,457 | 12,584 | 0 |
| CPO matched explore | 3,417 | 12,610 | 0 |
| GEPA dependencies | 2,913 | 13,460 | 0 |
| GEPA dependencies with merge | 2,887 | 13,376 | 0 |

Refresh replaced 48 probes and lost 20 matched critical passes against ordinary dependency-aware CPO. Exploration gained 50 passes and 36 matched critical passes against that baseline with 26 additional calls. It also gained 40 passes and preserved all matched critical passes against matched exploration while saving 26 calls.

The exploration result does not establish that the suggested edits were effective. The engine offered 14 hypotheses, started validation on seven, and fully validated none. Changing which prompts were evaluated changed the subsequent search trajectory. A follow-up would need to match the validation allowance so each offered hypothesis can earn a complete observation. The exploration arm cleared both GEPA controls on the local panel and failed the matched critical-case gate on the contextual panels against GEPA without merge. The shipped proposal and probe policies are unchanged.

## Reproduce

The probe override is an experimental patch so the pinned optimizer source remains usable for earlier sealed runs. Apply it in a disposable export, then use the seal printed by the preview command.

```sh
python -m pip install --require-hashes -r requirements-benchmark.txt
git apply --unidiff-zero benchmarks/patches/component-refresh.patch
PYTHONHASHSEED=0 python -m benchmarks.component_refresh
PYTHONHASHSEED=0 python -m benchmarks.component_refresh --execute PLAN_SHA256 --out result.json
```

Two runs produced byte-identical details with DNS and outbound sockets blocked. The [published summary](component-refresh-results-v1.json) includes costs, critical comparisons, intervention counts, source hashes, and the exact detail file hash.
