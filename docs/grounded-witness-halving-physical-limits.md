# Physical request ceiling for the sealed Halving comparison

The development comparison needs at most 2,712 distinct generation requests across its three tasks. The published futility plan allows 3,612 logical requests. The lower ceiling applies to provider calls after reuse of identical requests. All seven arms retain their logical quotas, prompts, case splits, ordering, and acceptance gates. A qualifying development run still completes its full scoring panel. Confirmation retains its separate seal and exact demand calculation. [Futility comparison](grounded-witness-halving-futility.md)

| Role | Original ceiling | Physical ceiling | Physical ceiling per task |
| --- | ---: | ---: | ---: |
| Reflection | 12 | 12 | 4 |
| Evaluation | 1,776 | 1,176 | 392 |
| Admission | 960 | 768 | 256 |
| Qualification | 864 | 756 | 252 |
| Total | 3,612 | 2,712 | 904 |

- **Witness and fallback evaluation.** The one-admission witness follows a prefix of the four-admission witness. Their journal reuses identical requests across arms, so four cycles of at most 30 calls cover both. The hybrid can add at most 16 evaluations.
- **Native GEPA evaluation.** Both modes stop after their first independent proof. Until that proof each mode starts each nonempty cycle with the same incumbent and eight validation anchors. The pinned GEPA engine grades those anchors first. Each of the eight possible mode-cycle runs can add at most 24 calls beyond the eight shared seed grades. This gives a ceiling of 200.
- **Halving evaluation.** With three valid prompts, the eight- and twelve-call controls schedule at most seven and twelve grades. Their first rounds share three grades. Two incumbent grades are already present in the GEPA anchors. Together they can add at most 14 calls per cycle, including when a control stops early. This gives a ceiling of 56.
- **Admission.** The shorter witness shares its first proof with the longer witness. The hybrid can attempt a separate proof only if the witness made none. That caps witness and hybrid proofs at four. The two GEPA modes and two Halving controls can each add one proof. Each proof grades two prompts over eight cases and two repeats.
- **Qualification.** If the witness issues a proof, the hybrid and one-admission witness freeze the same prompt. Otherwise the one-admission witness retains the initial prompt. Including the initial prompt yields at most seven distinct prompts over 18 cases and two repeats.

The derivation verifies the original portable plan seal. The tests exercise the GEPA anchor grades with GEPA 0.1.4 and enumerate every binary grade board for the scheduled Halving windows. The ceiling is structural. It supplies neither a live result nor an estimate of typical usage. [Derivation](../benchmarks/witness_halving_physical_limits.py) · [Tests](../tests/unit/test_witness_halving_physical_limits.py)

Run the derivation from the repository root with Python 3.12 and the pinned benchmark requirements.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.witness_halving_physical_limits
```

## SDK checkpoint rehearsal

The SDK launcher uses the same lower-budget plan when pausing before a token count. On resume it first recreates the SDK and benchmark journals from settled replies, then sends the withheld count and generation. The original provider and benchmark results matched their uninterrupted versions byte for byte. The qualifying fixture resumed after 40 settled pairs and sent 620 new pairs. The faulted-scoring fixture resumed after 385 and sent seven before the original futility gate stopped it. A dispatch with an unresolved reply could not resume. The qualifying archive bound the separate confirmation panel. The fixture exercises restart and accounting with zero provider requests. [Verification receipt](grounded-witness-halving-checkpoint-sdk-rehearsal-v1.json)

Six warehouse regimes are absent from both scoring panels. A separate offline audit identifies the missing branches and verifies an alternative eight-case confirmation schedule with the same critical, tier, and site counts. [Coverage audit](grounded-witness-regime-coverage.md)
