# Case-level evidence for the rotating-witness comparison

The rotating-witness rule retained its measured **26.4% lookup savings** against batched GEPA at cap 88. Its observed accuracy gain was **0.076 percentage points** with subjects weighted equally. Resampling distinct cases produced a 95% range of **−0.087 to +0.257 points**. The quality gain is uncertain under this resampling analysis. The original comparison passed its predeclared gate based on point estimates and dropping one subject at a time. [Original transfer](prompteval-rotating-witness-transfer.md) · [Case evidence receipt](prompteval-rotating-witness-case-evidence-results-v1.json)

The audit regenerated the full sealed receipt byte for byte. It reconstructed the final prompt's outcome for each held-out case in each episode. The replay scores 49,536 model-and-episode outcomes on 774 distinct physical cases across nine subjects. Each case contributes its paired scores from both models and all 32 seeds. Each of 4,096 draws resamples those complete case groups. The second analysis also resamples whole subjects. Both analyses weight subjects equally and use the same drawn cases for CPO and every control. [Runner](../benchmarks/prompteval_rotating_witness_case_evidence.py)

| GEPA comparison | Observed CPO accuracy gap | Cases resampled within fixed subjects | Subjects and cases resampled |
| --- | ---: | ---: | ---: |
| Batched, cap 88 | +0.076 pp | −0.087 to +0.257 pp | −0.140 to +0.273 pp |
| Batched, cap 80 | +0.193 pp | +0.037 to +0.359 pp | −0.005 to +0.405 pp |
| Best affordable fixed native point in each draw | +0.193 pp | +0.037 to +0.359 pp | −0.007 to +0.405 pp |

At the observed scores, batched GEPA at cap 80 is the strongest fixed native point within CPO's lookup budget. It used 39,560 lookups versus CPO's 41,359. On the fixed subjects, the CPO advantage at this operating point survives case resampling. The range includes zero when subjects can vary. The affordable-control calculation uses recorded lookup costs. It selects a native point with no greater aggregate cost than CPO in each draw.

An exact retrospective allocation could spend **40,476 lookups** and score **48.314%** mean accuracy, versus **48.214%** for CPO. It assigns deeper native search to clinical knowledge, high-school biology, and professional medicine and keeps the starting prompt for the remaining subjects. This allocation selects arms using held-out scores and describes what a perfectly informed budget allocator could do on these panels. The analysis still leaves fresh proposal generation and live-model effectiveness unverified.

## Reproduce

Use Python 3.12, the checked-in archive, and the hash-pinned GEPA 0.1.4 wheel. Verification used DNS and socket blocking and a disposable overlay bounded at 0.2 GiB under the standing LAB exception. Storage Guard measured 3.3 GiB free. [Benchmark wheel](../requirements-benchmark.txt) · [Pairing and allocation tests](../tests/unit/test_prompteval_rotating_witness_case_evidence.py)

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.prompteval_rotating_witness_case_evidence
PYTHONHASHSEED=0 python -B -m benchmarks.prompteval_rotating_witness_case_evidence \
  --execute c0f4a3df64269a1a82b97846472717cc0229ff915061ebfbcdfe7dbdad625bb2 \
  --out NEW_REPORT.json
```

The receipt SHA-256 is `70244addbc43a7e8a0716f1cd498eb3759e4adecfa61d5c02f0e8e884f93483c`.
