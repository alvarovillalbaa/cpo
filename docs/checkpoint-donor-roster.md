# Supply challengers from another checkpoint’s archived training replies

Widening MMLU qualification produced little held-out benefit. This experiment changes the offered prompts before search. It uses 30 archived MMLU model panels, with two aligned checkpoints per subject, and keeps the original incumbent and all target case splits. Source checkpoint grades are available only on each trial's target training case IDs. The recipient still needs a strict validation gain and the original independent qualification margin. [Previous qualification experiment](qualification-precheck-extension.md) · [Replay driver](../benchmarks/checkpoint_donor_roster.py)

The ranked roster takes the eight templates with the highest donor training score, excluding the incumbent. A seeded shuffle breaks ties. The mixed roster alternates four high-ranked donor templates outside the seeded roster with the first four seeded challengers. CPO uses the 19-lookup two-sided cycle on all three rosters. Both native GEPA modes receive the identical rosters and a sweep of search caps 6–180 with all six existing qualification wrappers. The native ceilings price only recipient lookups and allow one setting per subject shared across both checkpoints and all seeds. The combined menu lets each subject use any of the three rosters. [Validation cycle](two-sided-certificate-cycle.md) · [Prior GEPA comparison](paired-order-gepa-comparison.md)

## Results

Each entry gives held-out passes and paid recipient lookups. The GEPA entries are attainable subject-tuned scores within the corresponding CPO budget. [Sealed results](checkpoint-donor-roster-results-v1.json)

| Qualification gain | Roster | CPO | GEPA on the same roster | GEPA across all rosters |
| --- | --- | ---: | ---: | ---: |
| One | Seeded | 56,094 / 12,701 | 56,116 / 11,534 | 56,152 / 12,324 |
| One | Donor ranked | 56,088 / 12,739 | 56,079 / 5,910 | 56,152 / 12,324 |
| One | Mixed | 56,110 / 12,707 | 56,133 / 10,929 | 56,152 / 12,324 |
| Two | Seeded | 56,094 / 8,893 | 56,111 / 8,009 | 56,145 / 8,509 |
| Two | Donor ranked | 56,065 / 8,897 | 56,079 / 5,910 | 56,145 / 8,509 |
| Two | Mixed | 56,087 / 8,880 | 56,131 / 8,191 | 56,145 / 8,509 |

The mixed roster gained 16 passes at one gain on six extra recipient lookups. A separate audit resampled the held-out cases within each subject 4,096 times, keeping both checkpoints and all 32 schedules together for each case. The mixed roster's paired 95% range against seeded CPO was −18 to +52 passes. Omitting any subject left a point gain of +9 to +24 passes. Its one-gain ceiling with perfect knowledge of the available target candidates was 56,218 passes, 30 below the seeded roster under the same validation and qualification gates. The full donor roster also reduced that eligibility ceiling and lost six observed passes. Those diagnostics use held-out grades after selection and describe only the supplied templates. [Paired resampling helper](../benchmarks/recorded_sequential_certificate_screen.py)

GEPA improved by 17 passes on the mixed roster versus its seeded roster at the respective one-gain budgets. Its combined menu finished 42 passes ahead of the strongest observed CPO result and used 383 fewer recipient lookups. All three CPO arms lost to the combined menu at each margin. The donor policies remain benchmark-only.

The 960 shortlist constructions used 950,400 logical donor archive accesses for 467,544 distinct grades. Each pair was already present in the pinned archive. Both optimizers received the same shortlist, and the paid recipient comparisons assume an existing donor archive. No evaluation from that source was purchased during the replay.

## Reproduce offline

Use the pinned Python GEPA 0.1.4 benchmark dependency and a fresh output path. [Benchmark requirements](../requirements-benchmark.txt)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.checkpoint_donor_roster \
  --execute 5ec84793324e4b024988d5752cd40780f41f1b44c8f55d081fa87f2536f77095 \
  --out NEW_REPORT.json
```

Two socket-blocked runs from clean source produced identical reports at SHA-256 `cfe70a9c29ebd80e95007f0b258195bab69a07675cc6b371e01b0a4e95bf7d29`. They reproduced all 60 seeded CPO panel-by-margin traces, both published seeded native subject ceilings, and checked 6,300 native settings across the three rosters. Thirteen targeted tests passed. Storage Guard measured 1.9 GiB free. The hard-linked source exports, wheel overlay, and publication checkout fit the standing 0.2 GiB LAB exception. No provider requests were sent. [Targeted tests](../tests/unit/test_checkpoint_donor_roster.py) · [LAB storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
