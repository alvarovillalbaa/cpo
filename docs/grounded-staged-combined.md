# Compare both exact certificates in the staged CPO protocol

The combined protocol enables the opening certificate and the final-draft certificate. It binds both source hashes and retains the same cohorts, GEPA controls, admission, and holdout gates. The request ceilings are 1,272 for development and 192 for independent confirmation. Confirmation binds the exact combined development archive. [Runner](../benchmarks/grounded_staged.py) · [Opening certificate](opening-certificate.md) · [Final-draft certificate](opening-validation-certificate-transfer.md)

Both fixture profiles qualified in development and confirmation. The decisions and scores matched the final-draft-only protocol within each profile. The perfect-ticket profile removes the deliberate error from the ticket rewrite and keeps the other two rewrites faulted. [Rehearsal driver](../benchmarks/grounded_staged_combined_fixture.py) · [Detailed results](grounded-staged-combined-results-v1.json)

| Fixture profile | CPO search uses, final-draft only | CPO search uses, combined | Sequential GEPA | Batched GEPA | Physical development requests in either run |
| --- | ---: | ---: | ---: | ---: | ---: |
| All rewrites faulted | 165 | 165 | 197 | 174 | 624 |
| Perfect ticket rewrite | 152 | 143 | 178 | 171 | 548 |

Combined CPO scored 108 of 108 development replies and 48 of 48 confirmation replies in both profiles. The perfect-ticket shortcut removed nine CPO search uses. The shared run still sent the same physical requests because the GEPA arms also used those replies. This measures the two exact shortcuts on fixed replies. Provider cost and quality on fresh model replies remain unverified.

## Reproduce offline

Use GEPA 0.1.4 and fresh directories. The two-profile comparison is available through `python -B -m benchmarks.grounded_staged_combined_fixture --out NEW_REPORT.json`.

```sh
python -B -m benchmarks.grounded_staged --certify-opening --certify-final-draft \
  --fixture b3f2401e5752a728dfe606424d60ef6ceb611f294ff33ccb707ce20a4e1f0fd7 --out COMBINED_DEV
python -B -m benchmarks.grounded_staged --certify-opening --certify-final-draft --development COMBINED_DEV \
  --fixture 7b0aaee4339f98c9c15bb38c08add4bba2db2152f7ca4c9f5176af121303ea9d --out COMBINED_PANEL
python -B -m benchmarks.grounded_staged_case_evidence \
  --development COMBINED_DEV --confirmation COMBINED_PANEL
```

Two offline comparisons matched byte for byte. Twenty-five focused tests and four subtests passed. The public commands matched the two-stage archives, and the case-level audit verified confirmation. Storage Guard measured 6.3 GiB free, and the bounded scratch overlay was removed under the standing LAB exception. [Verification receipt](grounded-staged-combined-verification-v1.json)
