# Sealed staged comparison with exact final validation

The `--certify-final-draft` switch enables the published exact validation certificate in the staged CPO comparison. The plan binds that switch, the certificate source hash, and the full corpus hash. It keeps the same task splits, sequential and batched GEPA controls, shared admission, and development and confirmation gates. Its ceilings are 1,272 logical development requests and 192 logical confirmation requests. [Portable runner](../benchmarks/grounded_staged.py) · [Evaluated repair cycle](opening-validation-certificate-transfer.md)

The certified development fixture used 624 distinct physical replies, compared with 626 under full validation on the same inputs. The certificate eliminated three CPO search uses and two physical evaluations. The selected prompts, admission decisions, held-out outcomes, and both GEPA search counts matched. The certified independent fixture used 144 replies and matched the original holdout scores. Both fixture gates passed. [Plans and replay evidence](grounded-staged-certified-results-v1.json)

## Reproduce offline

Use GEPA 0.1.4 and fresh archive paths. The confirmation seal binds the exact certified development archive, including its delivery class. The runner rejects the use of a full-validation archive as certified development.

```sh
python -B -m benchmarks.grounded_staged --certify-final-draft \
  --fixture 487e9563ed6182400f78141fcc5100084e6dfc1399f755d3a39970d1de567159 --out CERTIFIED_DEV
python -B -m benchmarks.grounded_staged --certify-final-draft --development CERTIFIED_DEV \
  --fixture bc202e1f211f9fdff89e32a2b031c94726895434ebea3be9c053072135145414 --out CERTIFIED_PANEL
python -B -m benchmarks.grounded_staged_case_evidence \
  --development CERTIFIED_DEV --confirmation CERTIFIED_PANEL
```

Two rehearsals reproduced the archived hashes, and 13 focused tests passed with sockets and DNS disabled. Storage Guard measured 4.5 GiB free, and the 32 MB disposable source and fixture overlay was removed under the standing LAB exception. The original staged comparison has its own pinned source and seals. Provider performance of the certified comparison remains unverified. [Verification receipt](grounded-staged-certified-verification-v1.json) · [Original comparison](grounded-staged-comparison.md)
