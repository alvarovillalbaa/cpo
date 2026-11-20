# Transfer the eight-case opening screen to 30 archived panels

The eight-case screen with zero later proposer calls had the highest holdout score of the opening-only methods on the two recent transfer cohorts. This replay freezes that algorithm and moves it to 15 subjects outside those benchmarks. Each subject has two recorded model panels. The roster combines four existing PromptEval snapshots at the same pinned revision. The selection rule and roster were sealed before this comparison ran. [Opening screen](proposal-reflection-cap.md) · [Previous rescue experiment](proposal-opening-rescue.md) · [Transfer runner](../benchmarks/proposal_opening_transfer.py) · [Dataset license](../benchmarks/data/LICENSE.prompteval)

Each panel runs 32 four-cycle episodes. CPO’s screen starts from the supplied opening pair and scores its shortlist on eight cases. A shortlist winner must improve the total across all 24 validation cases and pass the original independent qualification before deployment. The policy keeps the 72-lookup search cap and calls no proposer after the opening. Both GEPA modes use their original proposal replay settings. Every arm uses the same starting prompt and seeded case schedule. The retain-start arm scores the untouched starting prompt on holdout. The accuracy gate requires improvement over retaining the start, a positive joint paired 95% range against both GEPA modes, and evaluation cost at or below both controls.

## Results

| Method across 30 panels | Holdout passes | Paid evaluation lookups |
| --- | ---: | ---: |
| Retain start | 30,141 | 0 |
| Original cap-72 CPO | 30,249 | 249,178 |
| Eight-case screen, zero later callbacks | 30,273 | 158,340 |
| CPO cap 171 | 30,259 | 634,504 |
| Sequential GEPA | 30,239 | 329,325 |
| Batched GEPA | 30,266 | 322,788 |

The eight-case screen gained 132 passes over retaining the start and 24 over original cap-72 CPO. It scored seven more passes than batched GEPA and used 164,448 fewer lookups, a reduction of 50.9%. It beat batched GEPA on 14 panels, tied on three, and scored lower on 13. The joint paired 95% range against both GEPA modes was −91 to +90 passes. Omitting one subject at a time put the smaller of the two GEPA score margins between −10 and +43 passes. The primary comparison cleared the cost condition and missed the accuracy condition.

| Snapshot | Panels | Eight-case passes / lookups | Batched GEPA passes / lookups | Retain-start passes |
| --- | ---: | ---: | ---: | ---: |
| PromptEval transfer | 6 | 4,468 / 31,265 | 4,481 / 61,350 | 4,456 |
| Episode budget | 8 | 11,639 / 41,103 | 11,619 / 85,514 | 11,523 |
| Requalification | 8 | 6,868 / 45,490 | 6,875 / 92,126 | 6,876 |
| Search coverage | 8 | 7,298 / 40,482 | 7,291 / 83,798 | 7,286 |

The screen used fewer lookups in every snapshot. Its holdout score beat batched GEPA in two of the four snapshots and the retained start in three. The archive supplies the opening pair and later proposals, so the lookup totals account for evaluations and qualification. Live proposal quality and generation cost remain unmeasured. CPO keeps its default search. [Panel counts, traces, and paired ranges](proposal-opening-transfer-results-v1.json)

## Reproduce offline

Use pinned GEPA 0.1.4 and a fresh output path. The repository contains the four hash-pinned input snapshots.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.proposal_opening_transfer
PYTHONHASHSEED=0 python -B -m benchmarks.proposal_opening_transfer \
  --execute 0daf2cab54f47fede4c278e1f94bfbde7526f9df2dae0c768c9c2fb27631956e \
  --out NEW_REPORT.json
```

Two clean source replays blocked sockets and DNS and matched byte for byte. Each ran 3,840 cycles of the frozen screen and independently repeated 60 GEPA panel traces. Six focused tests passed, covering full validation, independent qualification, and the hard reflection cap. The CLI rejected a stale seal and preserved an existing result. Storage Guard measured 5.6 GiB free. The 27.6 MB scratch export was removed under the standing LAB exception. [Verification receipt](proposal-opening-transfer-verification-v1.json) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
