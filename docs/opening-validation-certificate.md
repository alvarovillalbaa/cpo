# Certify the last staged repair against its measured anchor

The staged repair cycle fully evaluates the last draft against the opening. The alternative certificate starts with the already measured opening scores. Each unread challenger case can contribute either a pass or a failure. The certificate stops when these bounds prove strict total gain and nonregression in every family, with every protected critical pass observed. It also stops if strict gain or family preservation becomes impossible or a protected pass is lost. It uses cached challenger replies first, then reads protected rows before ordinary ones. [Package function](../cpo/anchored_validation.py)

The replay runs the original CPO cycle on the sealed panels, reconstructs its terminal validation boundary, and checks which final-draft replies were in the cache before that boundary. It releases the remaining archived fixture replies to the certificate only when requested. The terminal decision, selected candidate, and holdout passes are identical in all 144 trials. This isolates the certificate's lookup savings while keeping the original retry, holdout, and matched GEPA paths fixed. [Replay runner](../benchmarks/opening_validation_certificate.py) · [Per-panel evidence](opening-validation-certificate-results-v1.json)

| Confirmation panel | CPO passes | Original CPO calls | Calls with certificate | Sequential GEPA calls | Batched GEPA calls |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original faults | 648 / 648 | 2,286 | 2,261 | 2,524 | 2,282 |
| Shifted faults | 648 / 648 | 2,324 | 2,280 | 2,499 | 2,283 |

The certificate saves 25 and 44 reads in the two confirmation panels, closing the counted-call gap with batched GEPA. The fixture's accuracy and critical-case checks are unchanged. The function is available separately for callers with an already measured anchor. A later opt-in runs the certificate inside the repair cycle and reproduced these savings with actual fixture callbacks. The retained v5 live search stopped before recording any terminal staged repair, so provider savings remain unmeasured. [Original comparison](opening-residual-retry.md) · [Integrated transfer test](opening-validation-certificate-transfer.md)

## Reproduce

Use the source from commit `19b1c0647df5aaf0cda9c5e1f114e214ed1e783f` for this sealed report.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.opening_validation_certificate \
  --execute de53978e3dd64337bc98c6fa7d97f7f8fcfb0498d04ccf37be8728ba51d24ee0 \
  --out NEW_REPORT.json
```

Use pinned GEPA 0.1.4. Two offline replays matched byte for byte. Eleven focused tests passed with sockets and DNS blocked. The certificate tests include all 1,024 paired five-row outcome patterns with and without cached replies. The staged archive tests replayed the existing protocol. Storage Guard measured 4.5 GiB free, and the bounded 29.8 MB overlay was removed under the standing LAB exception. [Tests](../tests/unit/test_anchored_validation.py) · [Verification receipt](opening-validation-certificate-verification-v1.json)
