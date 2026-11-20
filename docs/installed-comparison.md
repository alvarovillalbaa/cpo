# Reproduce CPO comparisons from an installed wheel

An offline build from Git commit `7057ba6fe6c87ccca0b04827ba0625c3ba917466` produced `cpo-0.4.0-py3-none-any.whl` twice with identical bytes. The wheel was installed with pinned GEPA 0.1.4 in three fresh virtual environments. Every packaged Python file matched the source export. The verifier ran from outside the source tree with Python isolation enabled. [Build and installation receipt](installed-comparison-verification-v1.json)

| Python | Published reports reproduced byte for byte | Focused tests passed |
| --- | ---: | ---: |
| 3.10.21 | 3 | 17 |
| 3.12.14 | 3 | 17 |
| 3.14.7 | 3 | 17 |

The three comparisons cover limited opening replies, early rejection of the development panel, and the matched incumbent qualification precheck. The last replay reproduces 4,560 archived CPO and GEPA trial traces. The other two use deterministic fixture replies. The original report files provide the comparison targets. [Opening budget](opening-budget.md) · [Development qualification](development-qualification.md) · [Qualification precheck](qualification-precheck.md)

Local wheel installation used no package index and passed the dependency check. The verification processes blocked socket creation and DNS. Storage Guard measured 20.6 GiB free. The temporary source and all three environments used 57.8 MB under the standing LAB exception and were removed after verification. Fresh-model quality remains pending.

## Run the verifier

Run from a Git checkout containing this verifier and the recorded reports. Use the builder versions listed in the receipt and set `GEPA_WHEEL` to the local GEPA 0.1.4 wheel with the recorded SHA-256.

```sh
CPO_SOURCE="$PWD"
CPO_SCRATCH="$(mktemp -d)"
CPO_REVISION=7057ba6fe6c87ccca0b04827ba0625c3ba917466
mkdir "$CPO_SCRATCH/source"
git archive "$CPO_REVISION" | tar -x -C "$CPO_SCRATCH/source"
SOURCE_DATE_EPOCH="$(git show -s --format=%ct "$CPO_REVISION")" \
  python3.12 -m build --wheel --no-isolation --outdir "$CPO_SCRATCH/dist" "$CPO_SCRATCH/source"
python3.10 -m venv "$CPO_SCRATCH/env"
"$CPO_SCRATCH/env/bin/python" -I -m pip --isolated install --no-index --no-deps \
  "$CPO_SCRATCH/dist/cpo-0.4.0-py3-none-any.whl" "$GEPA_WHEEL"
"$CPO_SCRATCH/env/bin/python" -I -m pip --isolated check
"$CPO_SCRATCH/env/bin/python" -I -B "$CPO_SOURCE/benchmarks/installed_comparison.py" \
  --out "$CPO_SCRATCH/report.json"
```

The verifier checks installed module origins and bytes before running the existing comparisons. The output contains the interpreter and installed distribution versions, source fingerprints, and report hashes. [Verifier](../benchmarks/installed_comparison.py)
