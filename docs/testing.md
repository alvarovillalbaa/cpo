# Run the published CPO test suite

From a CPO checkout, use a dedicated Python environment and install the benchmark and test dependencies. The tested configuration used Python 3.12.14, GEPA 0.1.4, pytest 9.0.2, Optuna 4.5.0, and Node.js 26.8.2.

```sh
python -m pip install --require-hashes -r requirements-benchmark.txt
python -m pip install 'pytest==9.0.2' 'optuna==4.5.0'
PYTHONHASHSEED=0 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  python -B -m pytest tests -ra -p no:cacheprovider
node --test tests/test_recorded_holdout_requests.mjs tests/test_recorded_holdout_score.mjs
```

Pytest collects standalone tests and unittest classes. The Node tests cover request-slot construction and scoring recorded provider journals. These test commands use bundled fixtures and need no provider credentials. Reproducing research runs that reference a separate archive requires the exact source and archive identities in the individual reports.

## Verified source revision

A clean Git export of `34997318787b4610e7a68332830790b55e220c9e` passed **294 Python tests and seven Node tests**, with zero failures or skips. The standalone run used bundled fixtures and loaded no sibling research archive. It blocked socket creation and DNS in Python and blocked network entry points in Node. A fresh virtual environment using the documented dependency commands also passed all 294 Python tests and `pip check`.

Storage Guard measured 15.2 GiB free. The 30.5 MB source and wheel overlay and the separate 103.9 MB fresh environment and source export were removed under the standing LAB exception. [Verification receipt](published-test-suite-v1.json)

For a separate package check, the installed-wheel verifier compares the coverage-aware selector's choices and lookup accounting against its recorded benchmark. The suite and replay verify implementation behavior. Fresh-provider comparisons require their own live qualification. [Installed selector replay](covered-pool.md#verify-the-installed-selector)
