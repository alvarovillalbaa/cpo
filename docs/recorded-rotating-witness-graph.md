# Rotating witnesses on the recorded Sol proposal graph

The rotating-witness screen scored **339 held-out passes against the opening-only baseline's 382** when transferred from the PromptEval fixed pool to the archived typed-policy graph. Following parent-specific edits left the witness result at 339. A follow-up tried the recorded rewrite first with exact paired opening validation and preserved all 240 admission selections. It matched 382 passes for an estimated **$20.366520** at recorded rates. [Results and trace hashes](recorded-rotating-witness-graph-results-v1.json)

The replay preserves two sets of 40 seeds for each of ticket routing, warehouse release, and outage credits. Each path has four training, four validation, two independent admission, and two replay scoring cases. The 480 scoring uses draw from 36 distinct cases. The native GEPA 0.1.4 controls keep stable disjoint training and validation IDs. All controls reproduce their saved cap-56 trace hashes. All policies share the recorded opening and the same exact family and critical-case admission rule. [Original graph replay](recorded-replay.md) · [Corrected native GEPA controls](grounded-gepa-cache-controls.md)

The fixed witness arm screens the supplied rewrite and repair. The branch arm can request four later slots with two training replies from its current parent. It pays for training and uses only available recorded children to screen the next parent. The archive fixes those children by parent. The feedback shown during this replay cannot cause a new child to be generated. The two exploratory follow-ups apply the original exact family and critical-case gate to validation as well as admission. One tries the rewrite and then the repair if needed. The other first uses witness evidence to choose the order and reuses those reads in the proof.

| Method | Held-out passes | Search reads | Admission reads | Estimated cost |
| --- | ---: | ---: | ---: | ---: |
| Witness opening | 339 | 1,474 | 661 | $18.980400 |
| Witness with parent-linked continuation | 339 | 2,867 | 661 | $35.805000 |
| Exact paired opening proof | 382 | 1,317 | 793 | $20.366520 |
| Witness-ordered exact opening proof | 382 | 2,084 | 793 | $23.952648 |
| Original opening-only CPO | 382 | 1,517 | 793 | $21.673896 |
| Staged CPO | 382 | 2,031 | 793 | $27.219960 |
| Split-safe sequential GEPA, cap 56 | 382 | 4,108 | 793 | $46.811472 |
| Split-safe batched GEPA, cap 56 | 380 | 5,466 | 793 | $53.177904 |

Both witness arms lost 26 matched critical scoring uses against opening-only CPO. The branch arm requested 534 later slots, including 386 below the root and 162 with a historical reflection receipt. It changed zero nominees. Exact paired validation with either opener order recovered every original selection and admission outcome. The recorded order used 767 fewer search reads than the witness-ordered proof. [Replay driver](../benchmarks/recorded_rotating_witness_graph.py)

The recorded-order proof saved 6.03% against opening-only CPO and 2.28% against the earlier certified opening. It saved 13.17% against the published fixed-opening GEPA control on these paths, with a 10.73% minimum saving across the six task and seed-set groups. The earlier certified opening and fixed-opening GEPA figures come from the saved comparison. The paired proof matches the original opening-only selections path by path, which supplies the quality link to that comparison. The cheapest native point across the previously replayed fixed-cap frontier that matched the score and critical cases cost $29.003640. [Certified opening comparison](certified-opening-validation.md) · [Native cost frontier](grounded-gepa-cache-controls.md)

These estimates apply the recorded evaluator and proposal prices. The two exact proofs were chosen after the direct witness result, and the replay uses recurring cases and recorded edits. Fresh model quality, feedback-dependent proposal generation, and actual provider spend remain unverified.

The exact paired proof is available through an opt-in package cycle. [API and ARC/AIME transfer](paired-opening-cycle.md)

## Reproduce offline

Use the original local GEPA research and Sol archives and the hash-pinned GEPA wheel. The launcher restores the immutable CPO baseline and adds the released witness module by hash in a disposable overlay. The original plan, source files, journals, and receipts stay available in their original locations. The launcher blocks sockets and DNS. Storage Guard measured 8.3 GiB free, and the bounded overlay uses the standing LAB exception for up to 0.2 GiB.

```sh
python -B -m benchmarks.recorded_rotating_witness_graph --research-root ../gepa-research
python -B -m benchmarks.recorded_rotating_witness_graph --research-root ../gepa-research \
  --execute b3c8e74f7f60984af9737a6e47cf5f4d51a49e76f867f824a6b62c330a414caa --out NEW_REPORT.json
```

The final receipt SHA-256 is `2762ef941d09ba8e8b3911128d874f87807472a396816dd3ac659cfa46510092`. Adding the two proof arms reproduced the original arms' counts and trace hashes in every group. [Budget, feedback, and proof fallback tests](../tests/unit/test_recorded_rotating_witness_graph.py)
