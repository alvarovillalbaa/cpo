# Spend a bounded number of reads on a stronger validation certificate

The first-certificate rule saved lookups on every transfer cohort and lost held-out passes. This replay preserves its exact search prefix and keeps the first certified prompt as a fallback. It then uses up to one or two validation panels' worth of additional reads to seek a lower bound of two more passes than the incumbent, starting with the first certified prompt and then continuing through the original roster. A protected critical miss rules out a candidate. The bounds use only paid validation replies. [Frozen first-certificate transfer](recorded-first-certificate-transfer.md) · [Replay runner](../benchmarks/recorded_certificate_lookahead.py)

The stronger certificate is a lower bound against the incumbent. The first candidate's unobserved replies can still make its exact score higher. If the extra reads prove no stronger certificate, the first candidate remains the nominee. The policy preserves the original training reserve and allows only one challenger through training corroboration and independent qualification. Extra validation evidence can change the nomination. It cannot add another qualification attempt.

| Setting | First certificate passes / lookups | One-panel allowance | Two-panel allowance | One-panel joint range | Two-panel joint range |
| --- | ---: | ---: | ---: | ---: | ---: |
| AIME, eight-challenger rotation | 4,082 / 8,191 | 4,077 / 8,701 | 4,076 / 9,461 | −23 to +30 | −27 to +31 |
| ARC-AGI, eight-challenger rotation | 13,755 / 8,346 | 13,777 / 8,598 | 13,778 / 8,942 | −45 to +26 | −44 to +27 |
| MMLU transfer | 13,431 / 10,578 | 13,434 / 10,981 | 13,434 / 11,661 | −35 to +4 | −35 to +4 |
| BBH transfer | 2,054 / 8,102 | 2,054 / 8,628 | 2,054 / 9,277 | −81 to −14 | −81 to −14 |
| LMentry transfer | 822 / 4,354 | 857 / 4,704 | 889 / 4,985 | −9 to +38 | +25 to +68 |

The one-panel allowance recovered 22 ARC passes and maintained 19.7% fewer lookups than the cheaper matched GEPA control. Its paired quality interval crossed zero. On LMentry, the two-panel allowance scored 50 more passes than the stronger GEPA point score, but saved just 3.8% against the cheaper control. The one-panel allowance saved 9.2% against that control, 42 lookups short of the 10% threshold. BBH scored the same with either allowance, and AIME lost five or six passes relative to the first certificate despite buying more evidence. The broader result leaves the joint gate unmet. [All cohorts, native controls, and nomination counts](recorded-certificate-lookahead-results-v1.json)

A follow-up skipped some reads of the first certified prompt once those reads could no longer affect the nomination. It preserved every decision and left the LMentry cost threshold unmet. [Exact pruning replay](recorded-certificate-lookahead-pruning.md)

The 2,352 scheduled trials reuse the original AIME and ARC settings and all 26 transfer panels. The earlier results informed this intervention. These are retrospective measurements of prompt selection and carry no evidence about newly generated prompts.

## Reproduce

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. With DNS and sockets blocked, 32 targeted tests passed and two replays matched byte for byte. All original math and transfer panel totals and traces reproduced, the CLI rejected a stale seal, and the ordered live plan matched its manifest. Storage Guard measured 5.9 GiB free. The 39 MiB export and publication worktree fit the standing 0.2 GiB LAB exception. The replay made zero provider requests. [Budget and certificate tests](../tests/unit/test_recorded_certificate_lookahead.py)

```sh
export PYTHONHASHSEED=0
python -B -m benchmarks.recorded_certificate_lookahead
python -B -m benchmarks.recorded_certificate_lookahead \
  --execute fbd40792718f8b8be2f9f2d4edadd8c75a2072d3a9a1d1d3f3795276d244de32 \
  --out NEW_REPORT.json
```
