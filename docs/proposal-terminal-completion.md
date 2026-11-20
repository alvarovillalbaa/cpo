# Use the remaining budget to score the last challenger

The two-window proposal search spent substantially more than cap-72 CPO and found few additional holdout passes. The new audit found a cheaper place to spend. The existing proposal loop reserves calls for future training probes. By the time it stops on a partial challenger, the remaining budget can be too small to open another round while still being enough to finish the current challenger. [Two-window result](proposal-branch-stop.md)

Both policies reuse the cap-72 search. They act only when its final event left a challenger partially measured and the remaining allowance is too small to fund another fresh round. **Finish** reads the remaining validation replies when the complete suffix fits. **Certificate** uses the existing exact lower bound and can nominate as soon as paid evidence proves strictly more validation passes and protects critical passes. Each compares the last challenger with the original fully measured search nominee. The final nominee still faces separate expected-cost qualification against the incumbent on the original eight cases. [Runner](../benchmarks/proposal_terminal_completion.py) · [Exact challenger check](../cpo/challenger.py)

The replay keeps the published PromptEval cases, proposal blocks, and 72-lookup search ceiling. The baseline audit inspects the archived suffix to count opportunities. Neither policy has access to the unpaid outcomes in that audit. GEPA and the unchanged CPO controls reproduce their previous panel paths.

## Results

On the eight transfer panels, the cap-72 baseline stopped with a partially measured challenger in 492 of 1,024 cycles. Those cycles left 4,870 search lookups unused. A complete suffix fit in 482 cycles. With all archived grades visible for the audit, 173 challengers would improve on the selected nominee in validation and 46 would also beat the incumbent in independent qualification.

| Policy | Development passes / lookups | Transfer passes / lookups |
| --- | ---: | ---: |
| Original cap-72 CPO | 4,159 / 33,177 | 10,237 / 66,831 |
| Finish the challenger | 4,156 / 35,302 | 10,209 / 71,452 |
| Certify the challenger early | 4,156 / 34,844 | 10,209 / 70,529 |
| Sequential GEPA | 4,139 / 44,944 | 10,236 / 91,649 |
| Batched GEPA | 4,176 / 44,194 | 10,263 / 88,226 |

The certificate changed 171 search nominations on transfer, including 55 with unpaid validation cases remaining. It used 923 fewer lookups than full completion and reached the same holdout score. Compared with the original cap-72 route, it used 3,698 more lookups and scored 28 fewer passes despite 24 additional promotions. Batched GEPA scored 54 more passes and used 17,697 more lookups than the certificate. The joint paired 95% range against the two GEPA controls was −108 to −5. This benchmark leaves the two terminal policies experimental. [Panel results, audit counts, and paired ranges](proposal-terminal-completion-results-v1.json)

## Reproduce offline

Use pinned GEPA 0.1.4 and a fresh output path.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.proposal_terminal_completion
PYTHONHASHSEED=0 python -B -m benchmarks.proposal_terminal_completion \
  --execute 58e9617ae716809dedef496ba5ee41fd14759387b211b1dd5bac98b5ea1ed897 \
  --out NEW_REPORT.json
```

Two offline replays from the same clean source export matched byte for byte. The runs blocked sockets and DNS, exercised 3,072 experimental cycle paths, and reproduced 60 previously published panel-control traces. Nine focused tests passed, including critical-pass protection, reuse of previously paid replies, and hard lookup limits. The runner rejected a stale seal and preserved an existing report. Storage Guard measured 10.2 GiB free. The 26.3 MB scratch overlay was removed under the standing LAB exception. [Tests](../tests/unit/test_proposal_terminal_completion.py) · [Verification receipt](proposal-terminal-completion-verification-v1.json) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
