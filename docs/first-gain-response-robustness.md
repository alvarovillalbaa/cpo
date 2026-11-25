# Audit exact grading and reject malformed draft strings

The audit exercised the exact grader on every case enrolled in the sampled-feedback comparison and its independent confirmation panel. An exact answer earned all field credit. Wrong-type mutations included boolean and integer substitutions, numeric strings, and floating-point representations of integers. Duplicate-key mutations used an alternate JSON escape spelling of the same field name. [Independent confirmation panel](first-gain-regime-confirmation.md) · [Audit runner](../benchmarks/first_gain_response_robustness.py)

| Check | Count | Result |
| --- | ---: | --- |
| Exact answers | 360 | All accepted |
| Wrong-type substitutions | 1,962 | All rejected with zero field credit |
| Escaped duplicate keys | 984 | All rejected with zero field credit |

The pinned draft parser decoded a JSON-escaped lone surrogate to a Python string, then raised `UnicodeEncodeError` while checking the UTF-8 draft length. The original fixture reproduced the abort on the first paid CPO reflection. The new portable amendment rejects the entire unencodable draft and accounts for it as a spent reflection. Valid Unicode and the existing 1,600-byte limit retain their behavior.

In the amended fixture the malformed response remained in the journal at sequence 3. The CPO cycle spent its two draft attempts and enrolled only the valid draft. The comparison reached all 648 holdout requests within the original ceilings. With ordinary replies, the corrected native-feedback journal, audit, and result fields reproduced exactly. The amendment has its own seal. Existing Luna bindings still refer to their published portable plans. [Sealed audit and rehearsal](first-gain-response-robustness-v1.json) · [Sampled-feedback correction](first-gain-native-feedback.md)

## Reproduce offline

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. Preview the plan by running without arguments.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.first_gain_response_robustness \
  --fixture f7962c5ab75bd13c05698521fd15fdd6d5e513df8b67d938abe8520b53432125 \
  --out NEW_REPORT.json
```

Two socket- and DNS-blocked runs produced identical receipts at SHA-256 `ae37a27ff8c149d266a0918cbd5e9d9afd6d689b84e79ba5b6e8bd4acbbfa060`. All 22 focused tests passed, including lone high and low surrogates, valid paired Unicode, typed policy, and the native feedback and confirmation fixtures. The CLI refused a stale seal and an existing output path. Storage Guard measured 8.0 GiB free. The source export, verified wheel overlay, and publication checkout fit the standing LAB exception within 0.16 GiB. Zero provider requests were sent. [Focused tests](../tests/unit/test_first_gain_response_robustness.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
