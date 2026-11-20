# Compare CPO with and without later repairs in one run

This protocol adds opening-only CPO alongside staged CPO, sequential GEPA, batched GEPA, and the starting prompt. The opening-only policy screens the same shared rewrite and repair, applies the same admission rule, and requests no later proposals. For each task it selects after the three original search arms and before holdout scoring. The recorded Sol replay motivated this control because opening-only matched every staged selection with fewer lookups. [Recorded comparison](grounded-staged-recorded-opening.md) · [Runner](../benchmarks/grounded_staged_policy_comparison.py)

The archive records one sample per identical non-reflection request within a repeat and keeps the original shared opening for all four search arms. It records every search and admission use by arm, with the corresponding physical sequence, so shared requests can be counted once for the full run and attributed to each policy that used them. Both CPO policies face the existing quality and efficiency gates against the starting prompt and both GEPA controls. The direct comparison reports task-level differences, matched critical losses in each direction, and a range from paired case resampling.

Either CPO policy can open the independent confirmation panel by qualifying in development. The panel freezes all selected prompts and replays the entire development archive before binding its seal. It scores both policies and reports which passed both phases. The protocol has its own 1,644-request development and 240-request confirmation ceilings. The previous combined plan and its archives retain their original seals.

| Fixture profile | Development physical requests | Confirmation physical requests | Staged CPO passes in development / confirmation | Opening-only passes in development / confirmation |
| --- | ---: | ---: | ---: | ---: |
| Every opening rewrite needs repair | 624 | 144 | 108 / 48 | 80 / 34 |
| Ticket rewrite is already correct | 548 | 128 | 108 / 48 | 84 / 36 |

The added control required zero extra physical requests in these profiles. Both selected the same staged and GEPA prompts as the original fixture runs. The opening-only matches also reproduced the earlier ablation. This is a reproducibility check on fixed replies. Fresh provider responses and spending remain unmeasured. [Seals, archive hashes, and verification](grounded-staged-policy-comparison-results-v1.json)

## Reproduce offline

Use pinned GEPA 0.1.4 and fresh output paths. The example runs the fixture where every rewrite needs repair. Use `--profile perfect-ticket-rewrite` for both phases to run the other fixture.

```sh
python -B -m benchmarks.grounded_staged_policy_comparison
python -B -m benchmarks.grounded_staged_policy_comparison \
  --fixture 1c3c2cd7668bdc0cbe8e2e68cbe24ec85f12b451ace63571219857fdf6b5bf2e \
  --out DEV
python -B -m benchmarks.grounded_staged_policy_comparison --development DEV
python -B -m benchmarks.grounded_staged_policy_comparison \
  --development DEV --fixture PANEL_SHA256 --out PANEL
python -B -m benchmarks.grounded_staged_policy_comparison \
  --development DEV --replay PANEL --out PANEL_REPLAY
```

Use the seal printed by the preview for `PANEL_SHA256`. Each preview, fixture, and replay command works with sockets and DNS blocked. The four fixture archives replayed byte for byte, independent reruns reproduced both development archives, and 17 focused tests passed. Storage Guard measured 6.3 GiB free. The 35.6 MB scratch export was removed under the standing LAB exception.
