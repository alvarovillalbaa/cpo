# Sealed comparison for validation-guided repair

`portable-grounded-staged-v1` compares the published validation-guided CPO cycle, including its eight-probe retry, with native field-scored sequential and batched GEPA 0.1.4. It uses fresh instances of the ticket, warehouse, and outage policies. Each task has 16 labeled training cases, 12 validation cases, eight admission cases, 18 development holdout cases, and eight independent confirmation cases. Inputs are disjoint across splits and from the earlier portable grounded cohort. The policy templates are shared.

All three methods use one shared opening pair, the same labeled training, a 56-lookup search cap, and the same adaptive family certificate on admission. Only measured training rows enter the proposer’s feedback. The final development holdout tests the admitted prompts and the starting prompt, with two replies per case. A qualifying development archive must replay exactly before binding the confirmation panel and prompt hashes. [Runner](../benchmarks/grounded_staged.py)

The development ceiling is 1,272 logical requests. Independent confirmation has a ceiling of 192. Exact structured requests share one physical reply across arms, with admission and qualification separated by role and repeats separated by their indices. Search costs count each arm’s logical uses, including admission and the shared opening. Each physical request is flushed to the journal before calling the responder. A missing reply leaves an unmatched request and no completed result.

## Offline rehearsal

| Stage | CPO passes | Sequential GEPA passes | Batched GEPA passes | Physical fixture replies |
| --- | ---: | ---: | ---: | ---: |
| Development | 108 / 108 | 100 / 108 | 80 / 108 | 626 |
| Independent confirmation | 48 / 48 | 44 / 48 | 34 / 48 | 144 |

CPO cleared both scripted gates and preserved every matched critical pass. The fixture starts from a shared rewrite with a scripted error in each task. Two clean source rehearsals and an installed-wheel rehearsal reproduced both archives byte for byte. Nine focused tests passed in each environment, including lost-reply preservation, cohort isolation, rejection of a stale seal, and rejection of model confirmation against a fixture development archive. Storage Guard measured 4.6 GiB free. Scratch exports were removed under the standing LAB exception. [Rehearsal hashes](grounded-staged-rehearsal-v1.json) · [Verification receipt](grounded-staged-verification-v1.json)

The case-level audit groups repeat replies and reports how the comparison margins vary with the mix of holdout cases. The four extra confirmation passes against sequential GEPA came from two outage cases. [Paired case evidence and replay command](grounded-staged-case-evidence.md)

## Run the offline comparison

Use pinned GEPA 0.1.4 and fresh output paths. The second seal derives from the development archive’s exact bytes.

```sh
python -B -m benchmarks.grounded_staged \
  --fixture ceb5690febead7619a177aaba85134e6ffad27c37c6264c3ad1657129db315cb \
  --out STAGED_DEVELOPMENT
python -B -m benchmarks.grounded_staged --development STAGED_DEVELOPMENT
python -B -m benchmarks.grounded_staged --development STAGED_DEVELOPMENT \
  --fixture 5a71295645e40baa5595a448d5613bc78c6c006da532035685fc1abc0cb789ce \
  --out STAGED_CONFIRMATION
python -B -m benchmarks.grounded_staged --development STAGED_DEVELOPMENT \
  --replay STAGED_CONFIRMATION --out STAGED_CONFIRMATION_REPLAY
```

The Python runner accepts a caller-supplied text responder. The rehearsal uses a local deterministic responder with socket creation and DNS blocked. A model-backed launch requires an approved SDK route, a provider token reservation, and provider receipt verification. The paused v5 recovery is a separate sealed run. [Model-backed evidence](model-backed-validation.md)
