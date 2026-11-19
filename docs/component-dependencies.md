# Feedback reuse across component changes

Checking component dependencies eliminated all 284 stale diagnostic transfers seen when the archive checked only the edited component. It also reduced held-out passes from 3,718 to 3,517 out of 4,608. Exact-parent reuse passed 3,556 cases and used 106 more search calls than dependency-aware reuse. Keep dependency-aware reuse available for callers that require compatible evidence. These results do not support making it the default proposal policy.

## Protocol

Each panel used 16 seeds outside the pilot cohort, with 15 training, 12 validation and 36 held-out cases per seed. The four panels covered local diagnostics, a routing dependency, an approval dependency and the same routing dependency with its scope withheld. The routing pair deliberately shares its inputs so it can isolate the effect of withholding scope. Search used at most 96 or 144 distinct case evaluations, six scripted reflection slots and up to six training examples per round. Reported search calls include evaluations and reflection slots. The proposer reads diagnostics from measured training rows, and the benchmark reserves held-out rows for final scoring.

CPO compared exact-parent reuse, component-only reuse and dependency-aware reuse. GEPA 0.1.4 used the same dependency-aware proposer with and without its native merge operator. A declaration names which other prompt components the edit depends on. An empty declaration means the edited component determines compatibility. An unknown declaration requires the same full parent. The fixture records a transfer as stale when a dependency known to its grader changed. Actual dependency values feed only this audit. Transfer counts include recurring diagnostics across proposal slots.

## Results

| Search and reuse policy | Held-out passes | Search calls | Stale transfers |
| --- | ---: | ---: | ---: |
| CPO exact parent | 3,556 / 4,608 | 13,351 | 0 |
| CPO component only | 3,718 / 4,608 | 13,223 | 284 |
| CPO declared dependencies | 3,517 / 4,608 | 13,245 | 0 |
| GEPA declared dependencies | 2,851 / 4,608 | 13,811 | 0 |

CPO with declared dependencies cleared the qualification rule against both GEPA controls on the local panel at both evaluation caps. It missed that rule on every interaction panel. At cap 96, for example, it gained 84 passes over GEPA without merge on the routing panel while losing 53 matched critical passes. Against component-only CPO, the largest drop was 71 passes on the approval panel at cap 144. Aggregates count routing and unknown scope as separate planned panels.

GEPA native merge terminated on approval seed `58339` at both caps when `find_common_ancestor_pair` passed all-zero weights to `random.choices`. The first sealed invocation stopped at that exception. The recorded protocol revision retains the failure and compares only completed pairs for affected panels, with 15 of 16 pairs and qualification marked false. The official GEPA wheel was unchanged. The exact exception and per-seed outcomes are in the reproducible full output.

## Reproduce

Install the pinned dependencies in `requirements-benchmark.txt`. Run `python -m benchmarks.component_dependencies` to print the manifest. Then use `PYTHONHASHSEED=0 python -m benchmarks.component_dependencies --execute SEAL --out NEW_FILE` with its `planSha256`. The [result summary](component-dependencies-results-v1.json) includes the manifest, panel totals, matched critical losses, failed seeds and the full output hash. Two runs with DNS and outbound sockets blocked produced byte-identical results. The benchmark used deterministic fixture responses and no model inference.
