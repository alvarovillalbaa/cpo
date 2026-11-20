# Opening dominance on recorded ARC-AGI and AIME outcomes

The opening dominance proof preserved every CPO selection and held-out score across 760 replay paths. It used more paid reads in all four groups. The estimated ARC cost fell for the original incumbent and rose for the rotated incumbents. The savings observed on Sol did not transfer consistently. [Sol replay](opening-dominance.md) · [Transfer report](recorded-opening-dominance-transfer-results-v1.json)

| Archive and incumbent | Held-out passes with CPO | CPO reads, proof off → on | CPO archived cost, proof off → on | Fixed-rewrite GEPA passes / reads |
| --- | ---: | ---: | ---: | ---: |
| ARC original | 1,462 / 1,920 | 847 → 863 | $82.58 → $80.78 | 1,244 / 810 |
| ARC rotated | 13,738 / 17,280 | 5,987 → 6,212 | $764.75 → $793.40 | 13,373 / 4,355 |
| AIME original | 488 / 1,000 | 508 → 535 | Unavailable | 497 / 414 |
| AIME rotated | 4,044 / 8,000 | 4,642 → 4,757 | Unavailable | 4,073 / 3,206 |

CPO scored higher than all three GEPA controls on ARC. The least expensive control, fixed-rewrite GEPA, cost $75.11 with the original incumbent and $555.36 under rotations. Paired case resampling gave CPO a range of **+269 to +461 passes** against that control on rotated ARC. CPO used more reads and scored lower than fixed-rewrite GEPA on both AIME groups. The rotated AIME range was **−52 to −7 passes**.

On rotated AIME, fixed-rewrite GEPA retained the incumbent on 19 paths where CPO promoted a candidate. Those paths accounted for 73 of CPO's 98 gross paired losses and 55 of its 69 gains against that control. The net difference across all paths was −29 passes. On rotated ARC, CPO-only promotions went the other way, with 466 gains and 67 losses. A follow-up preserved fixed-rewrite GEPA's decisions while cutting paid reads on both archives. [Paired fixed-rewrite proof](recorded-paired-rewrite.md) · [Earlier admission study](recorded-training-corroboration.md)

## Design

The benchmark uses the bundled GEPA artifact matrices for Gemini 3 Flash on ARC-AGI and GPT-4.1 mini on AIME. It retains their existing 40 split seeds and evaluates both the original incumbents and rotations. The seed and incumbent ID pick the two common candidates without consulting grades. CPO uses a screen of two-thirds of validation, rounded up, and a ceiling of three paid reads per validation case across the three prompts. The ARC and AIME archives supply binary outcomes. Each archive is treated as one family.

The GEPA 0.1.4 controls use the same validation cache, with a two-case minibatch and the supplied rewrite or pair. Both native modes receive the same ordered pair. Each arm uses the same disjoint admission rule. Lookup totals include search and admission. ARC cost estimates sum recorded evaluator charges. The supplied proposals carry no additional charge in any arm. Held-out results reuse archived score cells across paths, and the resampling keeps all repeats of each original problem together. [Archive provenance and license](recorded-math-validation-ties.md#source-coverage)

## Reproduce offline

Use the published source and GEPA 0.1.4. The first command prints the seal. The second writes to a fresh output path.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.recorded_opening_dominance_transfer
PYTHONHASHSEED=0 python -B -m benchmarks.recorded_opening_dominance_transfer \
  --execute 0a612d1785a7cb4cea3857d5778837e84b271f093687b46902891f018c83d02c --out NEW_REPORT.json
```

Two socket- and DNS-blocked replays matched byte for byte. These results test fixed proposals on recorded scores. Fresh proposal generation and live-model superiority remain unverified.
