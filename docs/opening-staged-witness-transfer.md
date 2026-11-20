# Test a shorter opening probe batch on fresh interactions

The [staged repair comparison](opening-staged-repairs.md) was 28 calls above batched GEPA on its transfer cohort. A pilot saved enough calls by stopping the opening training batch at the first measured failure. Later stages could still read two probes to expose additional interacting rules.

The confirmation seals 36 fresh input panels. It tests their original fault locations and shifts the faulty entries in a second mode on the same inputs. Shifted panels also protect the cases that exercise a shifted entry. The controls share each mode’s inputs, critical labels, scripted proposer, and 56-lookup search ceiling. The confirmation requires the shorter opening batch to clear both GEPA gates in both modes. [Runner](../benchmarks/opening_staged_witness_transfer.py)

| Cohort | Staged repair passes / calls | Shorter opening passes / calls | Sequential GEPA passes / calls | Batched GEPA passes / calls |
| --- | ---: | ---: | ---: | ---: |
| Previously observed transfer | 640 / 2,667 | 638 / 2,633 | 562 / 2,883 | 521 / 2,639 |
| Fresh panels | 635 / 2,635 | 633 / 2,601 | 571 / 2,829 | 528 / 2,630 |
| Fresh panels with shifted faults | 607 / 2,735 | 599 / 2,700 | 567 / 2,988 | 514 / 2,716 |

The previously observed transfer reproduced the pilot pass against both GEPA controls. The shorter opening also cleared the batched gate on the fresh panels. It gained 62 passes and saved 228 calls against sequential GEPA on those panels, with three matched critical losses that blocked the sequential gate.

With shifted faults, the shorter opening saved 35 calls against ordinary staged repair and lost eight exact passes, all critical. It lost 13 matched critical passes against sequential GEPA and scored as low as 12 of 18 on one panel. Both GEPA gates failed in this mode. The experiment supports a cost saving and identifies a reliability loss when the repair must locate a different rule entry. The strategy remains in the scripted benchmark. [Sealed results](opening-staged-witness-transfer-results-v1.json)

In a diagnostic replay, all 11 panels with a matched critical loss against sequential GEPA stopped after a later pair of training probes both passed. They finished with 10–17 search lookups unspent. One panel also rejected the resulting repair chain on full validation.

The follow-up checked for remaining validation misses before paying for later probes. It cleared the sequential gate on new panels in both fault modes and finished within 19 calls of batched GEPA. [Validation-guided routing](opening-validation-routing.md)

## Reproduce offline

Use GEPA 0.1.4, the source at commit `bcd03259cc341c9d0ce689f57ba301e467b0076c`, and a fresh output path to reproduce the original seal.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.opening_staged_witness_transfer
PYTHONHASHSEED=0 python -B -m benchmarks.opening_staged_witness_transfer \
  --execute 28a0708099daa150b1fdd46e8588a40db2e16ba1809e2fea7186f57d862974df \
  --out NEW_REPORT.json
```

Two replays with sockets and DNS blocked matched byte for byte. Each covered 72 input panels across 108 panel and mode combinations and ran 216 native GEPA paths. Eighteen focused tests passed. The runner rejected an altered seal and preserved an existing report. Storage Guard measured 4.6 GiB free and the 29.6 MB scratch export was removed under the standing LAB exception. Live qualification remains pending. [Verification receipt](opening-staged-witness-transfer-verification-v1.json)
