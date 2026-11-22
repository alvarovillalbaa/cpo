# Order qualification using the other prompt’s reply

`run_paired_order_certificate_cycle` uses the deferred screen, threshold precheck, and the same exact qualification decision. On short noncritical qualification panels in one family, it can choose the next row using a reply already paid for on the other side of that row. [Public API](../cpo/paired_order_certificate_cycle.py) · [Deferred screen](deferred-certificate-cycle.md) · [Earlier paired-reply study](prompt-paired-reply-order.md)

```python
from cpo.paired_order_certificate_cycle import run_paired_order_certificate_cycle

result = run_paired_order_certificate_cycle(
    incumbent,
    candidates,
    validation_rows,
    qualification_rows,
    evaluate,
    metric_limit=19,
    qualify=qualify,
    minimum_gain=2,
)
```

For each unread reply, the scheduler starts with the marginal pass estimate from paid validation. If the partner grade is known, it averages that estimate with the partner’s outcome. It uses the original expected-cost calculation after each possible next reply, and actual qualification outcomes determine promotion or rejection. Critical cases, multiple families, and panels with more than eight rows use the original qualification order. The same precheck and two-replies-per-case limit apply throughout.

## Archived costs

The cap-19 replay covers 134 model panels, 32 schedules per panel, and two qualification margins. It preserved the validation callbacks, nominees, deployments, and held-out grades on all 8,576 paths. [Cost and callback fingerprints](deferred-certificate-paired-order-results-v1.json)

| Cohort | Lookups saved at one gain | Lookups saved at two gains |
| --- | ---: | ---: |
| BBH, original | 63 | 87 |
| BBH, other checkpoints on previously studied tasks | 39 | 36 |
| BBH, causal judgment | 5 | 9 |
| LMentry, original | 30 | 18 |
| LMentry, other checkpoints on previously studied tasks | 23 | 39 |
| LMentry, ends-with-word | 2 | 2 |
| Disjoint MMLU | 141 | 55 |
| Earlier MMLU | 156 | 80 |
| Total | 459 | 326 |

Across both margins, total lookup spend fell from 127,590 to 126,805. Individual paths varied. The replay spent less on 721 paths and more on 175. A separate replay gives GEPA the same scheduler and prices the expanded menu at the new CPO budgets. [Matched qualification-order comparison](paired-order-gepa-comparison.md)

## Reproduce

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.deferred_certificate_paired_order
PYTHONHASHSEED=0 python -B -m benchmarks.deferred_certificate_paired_order \
  --execute 26c6d64b3aa0d2df5e343eadcf2aecf4cbc0dc76db99165ab56693412632716d \
  --out NEW_REPORT.json
```

The public API reproduced every prototype subtotal and callback fingerprint. The clean source and installed wheel matched byte for byte at SHA-256 `d3b7875a8c6ab6a42add7eea10314870150fbc661df8c7c2161d5e117db9801e`. All 22 targeted source tests and two installed API tests passed, including exhaustive three-case boards at three margins and exact callback parity for critical cases. DNS and outbound sockets were blocked, and the CLI rejected the prototype seal before writing a report. Storage Guard measured 3.0 GiB free. The export, pinned GEPA test overlay, wheel, and publication worktree fit the standing 0.2 GiB LAB exception. [Replay driver](../benchmarks/deferred_certificate_paired_order.py) · [API tests](../tests/test_paired_order_certificate_cycle.py)
