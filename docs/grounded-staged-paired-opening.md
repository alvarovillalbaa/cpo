# Paired-opening development and confirmation protocol

This comparison adds the package's exact paired-opening cycle to the v6 staged protocol. It keeps the same task corpus and seeds, the common rewrite and repair, the staged and opening-only CPO controls, the two paired read orders, and the three native GEPA controls. Each task has disjoint training, validation, admission, development scoring, and confirmation rows. Native GEPA uses stable case identities across its training and validation stores. [V6 protocol](grounded-staged-policy-comparison-v6.md) · [Package cycle](paired-opening-cycle.md) · [Sealed portable plan](grounded-staged-paired-opening-plan-v1.json)

The new arm tries the shared rewrite before the repair and applies the exact family and critical-case proof to validation. Each task gets up to 36 validation reads for this arm, and it can send one nominee to independent admission. The portable journal reuses identical sampled replies and attributes their use by arm. Opening generation is attributed to all participating arms. SDK token pricing uses receipts for the actual shared or individual requests.

Development and confirmation require the new challenger to preserve task totals and matched critical cases against every native control and meet the existing quality or efficiency thresholds. The SDK binds a confirmation only when paired opening itself passed on both logical search uses and attributed token costs. The confirmation manifest binds the selected prompts and complete development archive hashes to a fresh panel.

## Rehearse offline

Use GEPA 0.1.4 and the v6 source revision for the controls. Overlay the two files below onto the exported revision. Fixture output contains scripted outcomes and stays in a separate directory.

```sh
cpo_checkout=$(pwd)
replay_dir=$(mktemp -d)
git archive 949dfe5e0971ce884b85026c76d1f96ad88e7ae0 | tar -xf - -C "$replay_dir"
mkdir -p "$replay_dir/cpo/paired_opening"
cp "$cpo_checkout/cpo/paired_opening/__init__.py" "$replay_dir/cpo/paired_opening/"
cp "$cpo_checkout/benchmarks/grounded_staged_paired_opening_comparison.py" "$replay_dir/benchmarks/"
(
  cd "$replay_dir" || exit
  PYTHONHASHSEED=0 python -B -m benchmarks.grounded_staged_paired_opening_comparison
  PYTHONHASHSEED=0 python -B -m benchmarks.grounded_staged_paired_opening_comparison \
    --fixture 3d6dfcaee13796276e6bca057cbe1bf9d087cc388d0ab3bde77ac05b483017f3 \
    --out "$replay_dir/fixture"
)
```

The physical request ceiling is 2,232 for development and 336 for independent confirmation. These are ceilings for this proposed protocol. Live provider evaluation remains paused.
