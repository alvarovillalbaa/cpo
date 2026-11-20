# Expose missing rules in the training probes

The prior staged repair found that demonstrations supplied the missing outage reason on every paid two-probe check. This version runs those two training probes with the instruction alone. Validation and qualification still evaluate the complete prompt, including its demonstrations. A failed probe can trigger one repair, which must improve full validation and preserve critical and family passes before it can enter independent qualification. [Staged repair benchmark](opening-screen-repair.md) · [Runner](../benchmarks/opening_repair_diagnostic.py)

The protocol replays the six prior seeds and freezes six additional seeds before running the comparison. Each cohort has 18 task panels across ticket routing, warehouse release, and outage credits. The primary test uses the additional seeds at a 56-lookup search cap. The earlier acceptance gate requires preservation of matched panel totals and critical passes, at least 14 exact passes on every panel, and either eight additional aggregate passes at equal or lower cost or at least 10% fewer calls. Calls include search and qualification lookups, the shared opening, and later proposals.

## Results at cap 56

| Method | Prior seeds passes / calls | Additional seeds passes / calls |
| --- | ---: | ---: |
| Opening screen | 297 / 970 | 292 / 974 |
| One repair, two standard probes | 305 / 996 | 315 / 1,024 |
| One repair, four standard probes | 314 / 1,048 | 322 / 1,062 |
| One repair, two instruction-only probes | 324 / 1,072 | 324 / 1,062 |
| Adaptive CPO | 324 / 1,122 | 324 / 1,083 |
| Sequential GEPA | 314 / 1,198 | 312 / 1,163 |
| Batched GEPA | 287 / 1,229 | 282 / 1,243 |

On the additional seeds, the diagnostic recovered 32 exact passes over the opening screen and nine over the matched two-probe control. It made 12 diagnostic probes across the six outage panels, observed an error on every probe, and accepted all six repairs. It scored 12 passes above sequential GEPA and 42 above batched GEPA, with 101 and 181 fewer calls, respectively. It preserved every matched critical pass and cleared the gate against both official GEPA modes. It matched adaptive CPO’s 324 passes and saved 21 calls.

At cap 40, the diagnostic also scored 324 passes on the additional seeds. It used 29 more calls than sequential GEPA and missed the cost condition. The same deterministic policy generator supplied both cohorts. Of the 324 holdout inputs on the additional seeds, 160 also occurred in some split of a prior seed. The results describe the controlled repair mechanism. Live proposal quality and cost remain unmeasured. [Outcomes, diagnostic receipts, and gate results](opening-repair-diagnostic-results-v1.json)

The opt-in repair API reproduces this diagnostic with a caller-supplied training prompt transform. [Opening-repair cycle API](opening-repair-cycle.md)

## Reproduce offline

Use pinned GEPA 0.1.4 and a fresh output path.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.opening_repair_diagnostic
PYTHONHASHSEED=0 python -B -m benchmarks.opening_repair_diagnostic \
  --execute 3a52c81a679af3fe0000d66699294496942e88bbed6e0bd32899cb122b359b22 \
  --out NEW_REPORT.json
```

Two clean source replays blocked sockets and DNS and matched byte for byte. Each checked 72 typed panel settings and reproduced 252 published reference paths. Thirteen focused tests passed, including the training-only transformation, restoring demonstrations for validation and qualification, and skipping probes for completed openings. The CLI rejected a stale seal and preserved an existing report. Storage Guard measured 4.7 GiB free. The 29.6 MB scratch export was removed under the standing LAB exception. [Tests](../tests/unit/test_opening_repair_diagnostic.py) · [Verification receipt](opening-repair-diagnostic-verification-v1.json) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
