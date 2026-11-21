# Order proof cases with earlier paid validation from another model

The previous replay found that a different case order could have brought 155 otherwise unaffordable MMLU certificates within budget. This experiment tests a rule that can choose case order before reading the target proof. It keeps paid search, the first proof, the rival, the two assigned panels, and the 24-lookup joint cap fixed. [Proof ordering audit](witness-rival-order.md) · [Runner](../benchmarks/witness_peer_case_order.py)

For each subject, both models advance through the same frozen seeds. Once both complete a seed, their distinct paid search grades become available to the other model's next episode. The scheduler pools earlier peer-model grades by physical case. It uses a smoothed pass rate and assigns a rate of one half to unseen cases. It reads lower-rate cases first for the incumbent and higher-rate cases first for the rival. Each side keeps its original order on ties. Holdout cases cannot enter the history. The exact score bounds and tie-extension rule still govern deployment.

Both models' search calls are charged to the same archived portfolio, which already includes both models. The experiment sends no extra calibration calls. The cost comparison applies to a portfolio that already runs both models. The second control rotates the same score values by one case within each panel to test whether matching a score to its case helps. The transfer gate requires a positive lower bound against both controls and spend within the seeded single-proof cost on every cohort.

## Results

| Cohort | Original case order passes / lookups | Rotated peer scores passes / lookups | Matched peer scores passes / lookups | Matched vs original paired 95% range, percentage points |
| --- | ---: | ---: | ---: | ---: |
| BBH and LMentry | 17,121 / 75,764 | 17,116 / 75,772 | 17,114 / 75,749 | −0.168 to +0.123 |
| MMLU prior subjects | 21,174 / 35,910 | 21,187 / 35,896 | 21,186 / 35,907 | −0.035 to +0.099 |
| MMLU additional subjects | 8,989 / 14,759 | 8,977 / 14,750 | 8,985 / 14,759 | −0.154 to +0.059 |

Peer scores gave the scheduler a way to reorder cases in 986 of 1,066 second attempts. The matched policy changed 39 deployments and added 11 rival promotions. It gained eight pooled MMLU passes and lost seven on BBH and LMentry. Total spend fell by 18 lookups relative to the original case order, while each cohort still exceeded seeded single-proof spend. The paired ranges against the rotated control included zero in every cohort. The policy failed the transfer gate. [All arms and paired ranges](witness-peer-case-order-results-v1.json)

## Reproduce

Use a clean source export with Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. With DNS and sockets blocked, 34 targeted tests passed and two full replays matched byte for byte. All original panel traces matched, the CLI rejected a stale seal, and the prospective live plan reproduced byte for byte. Storage Guard measured 5.5 GiB free. The source export, overlay, and publication worktree fit the standing 0.2 GiB LAB exception. [Ledger and proof tests](../tests/unit/test_witness_peer_case_order.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.witness_peer_case_order
python -B -m benchmarks.witness_peer_case_order \
  --execute 2903ec1aaabcda493c894547e2e63cbdf0b24088d708bbebccec6eed01749140 \
  --out NEW_REPORT.json
```
