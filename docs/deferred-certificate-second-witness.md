# Use a second paid witness to prioritize a challenger

The previous audit found that better challengers often fit the five-read proof reserve using the original shared probe. It did not establish an affordable way to put one of them first. This replay gives the first positive probe one more paid witness before deciding whether to continue that challenger's certificate. It keeps the 19-lookup validation cap, eight challengers, seeded case order, and separate exact qualification. It covers 134 model panels with 32 schedules each at both qualification margins. [Probe allocation and reachability audit](deferred-certificate-probe-allocation.md)

All arms take the extra read out of the existing proof reserve and reuse both paid grades in the exact certificate. The retention-first arm reads the first incumbent pass and keeps challenger priority. The retention-defer arm reads the same case and delays a challenger that misses it until after later positive probes. The gain-defer arm delays after a miss on the next case the incumbent also missed. A delayed challenger can return before the shared-probe misses if a certificate still fits. When the first probe can already certify or the second case is unavailable, the screen goes straight to the original proof. [Benchmark runner](../benchmarks/deferred_certificate_second_witness.py)

## Results

Each entry gives the change from the original shared probe in one-gain held-out passes and paid lookups. Positive lookup values mean higher cost. [Full results at both margins](deferred-certificate-second-witness-results-v1.json)

| Cohort | Retention first | Retention defer | Gain defer |
| --- | ---: | ---: | ---: |
| BBH, original | 0 / −92 | +33 / +235 | +5 / +544 |
| BBH, other checkpoints on previously studied tasks | 0 / −18 | −17 / +178 | −11 / +290 |
| BBH, causal judgment | 0 / −1 | 0 / +8 | 0 / −10 |
| LMentry, original | 0 / −22 | +73 / +247 | +38 / +332 |
| LMentry, other checkpoints on previously studied tasks | 0 / −4 | +34 / +191 | −12 / +204 |
| LMentry, ends-with-word | 0 / +1 | +31 / +67 | +53 / +60 |
| Disjoint MMLU | 0 / −21 | 0 / +41 | −19 / +35 |
| Earlier MMLU | 0 / −40 | +3 / +24 | −8 / +103 |
| **Total** | **0 / −197** | **+157 / +991** | **+46 / +1,558** |

At two gains, retention defer added 126 passes and 763 lookups. Gain defer added 89 passes and 1,476 lookups. Neither deferral improved the held-out score at equal or lower cost in any cohort at either margin. At one gain, both deferrals still trailed an affordable paired-order GEPA schedule on the two previously studied BBH cohorts and both MMLU cohorts. The earlier rotation remained cheaper and added more one-gain passes in aggregate. [Published paired-order GEPA schedules](paired-order-gepa-comparison.md) · [Rotation results](deferred-certificate-probe-allocation.md)

Retention first preserved every recorded nominee and deployment, saving 197 lookups at one gain and 184 at two gains. That is evidence for changing read order on these panels. Under a finite search cap, a different proof order can leave a different allowance for later challengers. The experiment gives no general deployment equivalence guarantee. The selector stays benchmark-only and the live-model comparison remains pending.

## Reproduce offline

Use the pinned GEPA 0.1.4 wheel and a fresh report path. Two socket-blocked replays from clean source reproduced the 268 shared-probe panel-by-margin traces and matched byte for byte at SHA-256 `9e9ae32d1e9e692938b4f88a8f031e101516c1bd886cbdcb05864e98b918eca0`. The runner checked exact gate decisions and reconciled both caps against charged lookups for each experimental path. Nine targeted tests passed, including a priority reversal and a delayed challenger that returned using both paid witnesses. Storage Guard measured 1.2 GiB free. The disposable overlay and publication checkout fit the standing 0.2 GiB LAB exception. No provider requests were sent. [Focused tests](../tests/unit/test_deferred_certificate_second_witness.py) · [LAB storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.deferred_certificate_second_witness \
  --execute 9435398f8048349f3c012bf37b159729ee8a93ae3f28bb7a36ce004da73ec18e \
  --out NEW_REPORT.json
```
