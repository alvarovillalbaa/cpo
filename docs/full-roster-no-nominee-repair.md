# Measure which missing math nominees one additional reply can recover

The full-roster precheck improved lookup cost while leaving the AIME score gap intact. This replay reproduces its paid traces over all 1,520 AIME and ARC-AGI trials, then separates two sources of missed passes. A hindsight veto can keep the incumbent after a harmful promotion. A hindsight nomination can choose any enrolled prompt with a strict gain on the original admission cases. The latter knows the entire archive and pays no discovery cost. [Prior transfer](full-roster-precheck-math.md) · [Benchmark](../benchmarks/full_roster_no_nominee_repair.py)

On the eight-challenger AIME rotation, vetoing harmful promotions in hindsight could return 44 gross passes while retaining 33 passes from beneficial promotions. Better proof-eligible prompts offered up to another 345 passes beyond that veto, including 206 in trials with no nominee. The larger gap lies in finding a candidate that can pass the existing admission gate.

## Paid repair rule

When the full-roster runner produces no nominee, the candidate rule first checks the observed admission ledger. Four incumbent passes close the gate for a strict gain. Otherwise the rule looks for a paid validation repair with no observed paired loss. When the ledger has no such candidate, it buys at most one unanswered challenger reply on an already-paid incumbent miss, subject to the 19-read validation allowance. Candidate and case order are fixed. A successful repair still faces exact independent admission. This reuses incumbent admission replies already paid on the trial.

The archive contained 45 already-paid witnesses. All 45 were in trials where the incumbent passed every admission case. The optional probe bought 103 validation replies and found six further witnesses. Six qualification attempts produced four deployments. The rescue rule left every original promotion in place.

| Archive and setting | Held-out pass change | Additional lookups |
| --- | ---: | ---: |
| AIME, root, four | 0 | 6 |
| AIME, root, eight | 0 | 3 |
| AIME, rotated, four | 0 | 9 |
| AIME, rotated, eight | +3 | 49 |
| ARC-AGI, root, four | +26 | 5 |
| ARC-AGI, root, eight | 0 | 2 |
| ARC-AGI, rotated, four | −2 | 12 |
| ARC-AGI, rotated, eight | −2 | 52 |

The archived gains concentrate in one ARC-AGI root deployment. Both ARC-AGI rotations lose two passes. On the eight-challenger AIME rotation, the rescue scored 4,048 in 3,605 lookups, versus 4,067 in 2,857 for the best affordable GEPA setting. The paired 95% range against GEPA was −62 to +24 passes. The range against unmodified full-roster CPO was −2 to +8. The opt-in runner retains its published rules. Live superiority remains unverified. [Trial attribution, proof charges, and matched GEPA results](full-roster-no-nominee-repair-v1.json)

## Reproduce offline

Use Python 3.12 and the hash-pinned GEPA 0.1.4 wheel. The replay uses the original four-case qualification assignment and held-out cases for every method.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.full_roster_no_nominee_repair \
  --execute de3070de7c6455d362a9a44e1d595d25b3363d734643ab288db40d8656d1001a \
  --out /tmp/cpo-full-roster-no-nominee.json
```

Two network-disabled replays produced byte-identical receipts. All 84 focused tests passed, including the closed-gate check, original validation cap, and qualification reply reuse. Storage Guard measured 8.9 GiB free. The source export, pinned wheel overlay and publication checkout fit the standing 0.2 GiB LAB exception. Teardown was verified. [Tests](../tests/unit/test_full_roster_no_nominee_repair.py) · [Storage authorization](../../lab/docs/runbooks/lab-storage-exceptions.md)
