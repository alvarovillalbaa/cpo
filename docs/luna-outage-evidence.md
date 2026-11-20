# Outage evidence in the retained Luna runs

The recorded GPT-6.2 Sol comparison at search cap 36 showed three critical loss observations against GEPA across two unique outage cases. One case involved a long outage with posted evidence and appeared once against each GEPA mode. The other involved a long outage with missing evidence and appeared against sequential GEPA. Long means 120 minutes or more. The earlier panel-allocation audit found that each losing split lacked the relevant condition across all nine development cases. [Allocation audit](recorded-critical-allocation.md)

## Verified live evidence

The completed GPT-6 Luna v1 study reproduced all 707 requests, including the matched outage holdout. Each arm had six outcomes on long outages with missing evidence and eight on long outages with posted evidence, across two repeats per case. Every arm scored zero exact passes in both conditions. The one exact outage pass from each GEPA arm was on an ordinary case under 30 minutes with posted evidence. The v1 study retained its original critical labels. Its completed trial failed development.

The pending GPT-6 Luna v5 recovery reproduced the retained 163 replies and verified the original plan, journal hash, and recovery seal. The outage opening reached its output cap before any outage evaluation. The archive contains **zero outage evaluation replies and zero qualification replies**. The recovery claim was absent at verification.

## Sealed v5 coverage

Cells count planned critical cases. The four common demonstrations are a subset of training. The independent panel has its own seal and can bind only after qualifying development.

| Historical loss condition | Training | Common demonstrations | Validation | Development holdout | Independent confirmation |
| --- | ---: | ---: | ---: | ---: | ---: |
| 120+ minutes, posted evidence | 4 | 1 | 3 | 5 | 1 |
| 120+ minutes, missing evidence | 2 | 1 | 2 | 2 | 1 |

The sealed v5 study covers both conditions that were absent in the losing Sol splits. Each condition has one independent case, so the panel offers a matched check on those two cases. It leaves condition-wide performance open. [Machine-readable evidence and source hashes](luna-outage-evidence-v1.json)

## Reproduce offline

Use the original GEPA research and Open Evals archives, Python 3.12.14, and the hash-verified GEPA 0.1.4 wheel overlay. Run from outside the CPO checkout. Set `CPO_AUDIT_SOURCE` to the current checkout, `CPO_RECORDED_EXPORT` to the recorded source revision in the receipt, and `CPO_V1_EXPORT` and `CPO_V5_EXPORT` to the corresponding pinned CPO source exports. Use resolved paths for the exports.

```sh
PYTHONPATH="$CPO_RECORDED_EXPORT:$GEPA_WHEEL_OVERLAY:$GEPA_RESEARCH" \
  python -B "$CPO_AUDIT_SOURCE/benchmarks/luna_outage_evidence.py" recorded
PYTHONPATH="$CPO_V1_EXPORT:$GEPA_WHEEL_OVERLAY:$GEPA_RESEARCH:$CPO_RECORDED_EXPORT" \
  python -B "$CPO_AUDIT_SOURCE/benchmarks/luna_outage_evidence.py" luna-v1 \
  --study-root "$GEPA_RESEARCH/docs/results/2026/11-19"
PYTHONPATH="$CPO_V5_EXPORT:$GEPA_WHEEL_OVERLAY:$GEPA_RESEARCH:$CPO_RECORDED_EXPORT" \
  python -B "$CPO_AUDIT_SOURCE/benchmarks/luna_outage_evidence.py" luna-v5 \
  --study-root "$GEPA_RESEARCH/docs/results/2026/11-19"
```

Each phase produced byte-identical reports on two socket- and DNS-disabled runs. Eight boundary checks covered 29, 30, 119, and 120 minutes in both archive input formats. Storage Guard measured 17.5 GiB free. The 18.9 MB source and wheel overlay and replay scratch were removed under the standing LAB exception. No inference was dispatched. [Audit runner](../benchmarks/luna_outage_evidence.py)
