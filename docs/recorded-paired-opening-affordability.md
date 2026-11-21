# Fund exact repair validation from its minimum required reads

The bound saved **1,626 paid lookups** at the 2.5× cap compared with spending the remainder blindly. Both methods nominated and admitted the same prompts on every replay path. Compared with the existing full-reserve rule, the bound spent more on all four archived cohorts. Only rotated ARC improved, and its gain came from one changed admission. These results favor keeping the current reserve rule. [Sealed results](recorded-paired-opening-affordability-results-v1.json) · [Runner](../benchmarks/recorded_paired_opening_affordability.py)

The cycle gives the rewrite the same fully funded proof as before. When the rewrite fails and the remaining budget cannot fund every missing repair grade, the new variant counts the fewest favorable paid replies that could still certify the repair. Only an observed incumbent miss or repair pass raises a family's lower gain bound. The bound requires enough favorable replies to make each family nonnegative, cover unresolved critical cases, and give a strict total gain. Paid incumbent replies carry forward. The variant stops once even favorable replies could no longer fit the remaining cap. Actual observed grades must prove validation before the same separate admission can run.

## Recorded results at the 2.5× cap

Each cell gives held-out passes and estimated ARC evaluator cost or AIME paid lookups, including admission. The benchmark reuses the original proposal pairs and seeded splits across 760 paths. Native GEPA receipts come from the hash-pinned paired-opening comparison. The replay independently verifies every same-cap reserve count and trace. [Parent benchmark and control provenance](paired-opening-cycle.md)

| Cohort | Existing reserve | Spend remainder blindly | Minimum required reads | Sequential GEPA | Batched GEPA |
| --- | ---: | ---: | ---: | ---: | ---: |
| ARC original | 1,448 / $80.20 | 1,448 / $81.50 | 1,448 / $80.91 | 1,395 / $95.17 | 1,401 / $109.93 |
| ARC rotated | 13,730 / $798.11 | 13,743 / $941.93 | 13,743 / $821.64 | 13,508 / $715.88 | 13,507 / $725.14 |
| AIME original | 490 / 547 | 490 / 631 | 490 / 562 | 497 / 536 | 497 / 525 |
| AIME rotated | 4,070 / 4,310 | 4,069 / 5,142 | 4,069 / 4,614 | 4,073 / 4,322 | 4,073 / 4,352 |

The repair crossed validation 13 additional times at this cap. Independent admission kept two, one in rotated ARC and one in rotated AIME. Against the same-cap reserve, rotated ARC gained 13 passes and lost six matched scoring uses. Its case-resampled 95% range was +4 to +22 passes, conditional on the fixed replayed paths. Rotated AIME lost one net pass, with a range of −4 to +2. The fixed-rewrite GEPA control scored 4,073 on rotated AIME with 3,206 paid lookups. The bounded fallback used 1,408 more and scored four fewer.

At the 2× cap, the bound bought zero additional lookups and reproduced the reserve rule on all paths. Both archives have one family and no critical rows. On such a panel of `n` cases, exact rewrite rejection consumes at least `n` unfavorable replies. Any `f` known incumbent misses needed additional reads. The repair still needs at least `n + 1 − f` favorable replies to prove a strict gain, so the joint minimum exceeds `2n`. The proof applies to a previously empty validation ledger. The tests also cover mixed families and critical rows with exhaustive small panels.

## Reproduce

Use Python 3.12 and hash-pinned GEPA 0.1.4. The historical export supplies the unchanged controls and archives. Verification blocked DNS and sockets and used a disposable allocation of at most 0.2 GiB under the standing LAB exception. Storage Guard measured 6.1 GiB free. The study used zero new provider requests and leaves fresh-model performance unverified. [Benchmark requirement](../requirements-benchmark.txt) · [Exhaustive tests](../tests/unit/test_recorded_paired_opening_affordability.py)

```sh
cpo_checkout=$(pwd)
replay_dir=$(mktemp -d)
git archive 100c8697f6ed3fe3959d7c9cab91b49f9cf277f7 | tar -xf - -C "$replay_dir"
mkdir -p "$replay_dir/cpo/paired_opening"
cp "$cpo_checkout/cpo/paired_opening/__init__.py" "$replay_dir/cpo/paired_opening/"
cp "$cpo_checkout/benchmarks/recorded_paired_opening_transfer.py" \
   "$cpo_checkout/benchmarks/recorded_paired_opening_affordability.py" "$replay_dir/benchmarks/"
cp "$cpo_checkout/docs/recorded-paired-opening-transfer-results-v1.json" "$replay_dir/docs/"
(
  cd "$replay_dir" || exit
  PYTHONHASHSEED=0 python -B -m benchmarks.recorded_paired_opening_affordability \
    --execute 58ceb9670aac1dd28f0f0cc8b7a1ef5ee2f82247706cadd12d1cf7cece0b5ff4 \
    --out "$cpo_checkout/NEW_REPORT.json"
)
```

The results SHA-256 is `298ef8af6d2eaa926ee9f7bd6bf742c5bc1c41945c20fb9f4443cb44ddb619a3`.
