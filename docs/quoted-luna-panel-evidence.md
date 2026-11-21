# Read the quoted Luna panel verdict and paired quality evidence

The sealed independent panel has 24 cases across three tasks and two replies per case and arm. Its operational gate checks pass floors, task regressions, and matched critical losses. Against each GEPA control it accepts either four extra passing replies or at least 10% lower search charge with every case total preserved. The replayed qualifying fixture tied all 24 case totals against both controls and passed on efficiency. [Verified fixture and boundary calculations](quoted-luna-panel-evidence-v1.json)

The paired report counts improved, regressed, and tied cases and retains matched critical losses at the individual reply level. For each control it sums the two reply differences within a case, then calculates the exact upper tail across possible independent swaps of the two arm labels by case. A claim of higher quality against both controls uses the larger of the two p-values. This calculation assumes independent case-level label exchangeability under each null. It describes the fixed admitted prompts for the three tasks. Generalization across search seeds and new tasks needs further evidence. [Case evidence software](../benchmarks/grounded_panel_evidence.py)

| Panel outcome against each control | Operational gate | One-sided case-level p-value |
| --- | --- | ---: |
| Every case ties and CPO costs 10% less in search | Pass | 1.00000 |
| Four extra passes from two cases | Pass | 0.25000 |
| Four extra passes from four cases | Pass | 0.06250 |
| Five extra passes from five cases | Pass | 0.03125 |

The three gain examples have no observed losses. Across all feasible case-difference patterns for this panel, the smallest one-sided p-value at exactly four additional passing replies is **0.0625**. A pass at that effect therefore leaves 5% case-level quality evidence inconclusive under the stated assumptions. The efficiency result describes the measured tradeoff on the panel and does not estimate an equivalence margin for future cases.

The evidence reader requires a complete panel and the sealed task, case, repeat, arms, and critical flags. Eight tests compare its exact distribution to exhaustive label swaps and verify that malformed or incomplete rows fail. The local SDK rehearsal replayed the original confirmation journal before deriving the report. The original gate and seals were preserved. Inference remains paused and the model-backed panel is unmeasured.
