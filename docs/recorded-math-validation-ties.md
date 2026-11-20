# Transfer witnessed validation ties to ARC-AGI and AIME

The four-read tie rule improved final scores on some prompt archives and lost passes on the earlier MMLU pilot. This replay tests the same tie proof on two different task families using GEPA's published recorded outcomes. ARC-AGI supplies ten Gemini 3 Flash architectures on 80 problems and recorded evaluator costs. AIME supplies nine GPT-4.1 mini candidates scored on 45 validation problems. Both pools appeared in earlier fixed-pool studies. This is a transfer of the tie rule to those pools. [Prompt-archive study](routed-validation-ties.md) · [ARC-AGI source](https://github.com/gepa-ai/optimize-anything-artifact/blob/main/acm_cais_artifact_evaluation/domains/arc_agi/logs/candidate_eval_results.json) · [AIME source](https://github.com/gepa-ai/optimize-anything-artifact/blob/main/acm_cais_artifact_evaluation/domains/aime_math/logs/run.log)

Each arm receives the same four- or eight-challenger roster in a seeded order. The 40 seeds per archive preserve the earlier holdout split. ARC uses 18 training, eight validation, six independent qualification and 48 holdout cases. AIME uses 10, six, four and 25, respectively. The root starts at the original ARC architecture or first fully observed AIME candidate. Rotation uses every other candidate as incumbent in turn. [Reduced scores and source receipts](../benchmarks/data/gepa-recorded-math-v1.json) · [Source license](../benchmarks/data/LICENSE.gepa-artifact)

The strict CPO arm races exact validation scores. The tie arms use the original witnessed proof when that race retains the incumbent, with either zero or four extra lookups. Every nominee needs a strict independent qualification gain. The controls use official sequential and batched GEPA 0.1.4 with the same roster, evaluation ceiling, and qualification. They use training evidence in GEPA's own search. Costs include paid search and qualification. ARC's cost column sums the historical cost attached to each measured cell. AIME supplies lookup counts. [Runner](../benchmarks/recorded_math_validation_ties.py)

The comparison requires a nonnegative lower endpoint for the joint paired holdout range against both GEPA modes, at least 10% fewer lookups, and no historical cost increase on ARC. The 4,096 draws resample the original problem IDs and keep all occurrences of a problem paired across seeds and incumbents. The archive scores recur across splits and may have influenced the original search.

## Results

Each cell shows holdout passes / paid lookups. The gate applies to the four-read policy. Strict CPO had the same gate outcome in every configuration.

| Archive and challengers | Strict CPO | Complete ties in up to four reads | Sequential GEPA | Batched GEPA | Gate |
| --- | ---: | ---: | ---: | ---: | --- |
| ARC root, four | 1,561 / 1,308 | 1,561 / 1,308 | 1,553 / 1,603 | 1,565 / 1,706 | Inconclusive |
| ARC root, eight | 1,578 / 1,507 | 1,578 / 1,507 | 1,558 / 2,230 | 1,562 / 2,171 | Inconclusive |
| ARC rotated, four | 13,878 / 8,636 | 13,889 / 8,895 | 13,755 / 9,296 | 13,695 / 8,798 | Failed |
| ARC rotated, eight | 13,932 / 10,383 | 13,937 / 10,495 | 13,785 / 14,790 | 13,781 / 13,023 | Passed |
| AIME root, four | 486 / 1,016 | 488 / 1,087 | 493 / 1,175 | 491 / 1,085 | Failed |
| AIME root, eight | 476 / 1,422 | 475 / 1,492 | 491 / 1,836 | 494 / 1,794 | Failed |
| AIME rotated, four | 4,036 / 7,726 | 4,044 / 8,249 | 4,079 / 9,021 | 4,067 / 8,444 | Failed |
| AIME rotated, eight | 4,002 / 11,166 | 3,999 / 11,549 | 4,074 / 14,016 | 4,055 / 13,640 | Failed |

On ARC with rotated incumbents and eight challengers, **strict CPO already cleared the gate**. It led sequential GEPA by 147 passes with 29.8% fewer lookups and 25.4% lower historical cost. It led batched GEPA by 151 passes with 20.3% fewer lookups and 14.1% lower historical cost. The joint paired range was **+52 to +241 passes**. Removing any one incumbent left a lead of at least 88 passes over sequential GEPA and 100 over batched GEPA at observed totals.

The four-read rule added five passes to strict CPO at the cost of 112 lookups in that configuration. Its paired range against strict CPO was −2 to +12. It also cleared the GEPA gate with a joint range of +51 to +250. At four challengers and rotated starts, both CPO settings had higher historical cost than batched GEPA. All four AIME configurations missed the gate. At eight challengers and rotated starts, the four-read rule's joint range was **−126 to −25 passes**. The result supports fixed-pool CPO selection on a specific ARC archive and gives mixed evidence for adding ties. Fresh generation and fresh-task performance remain unverified. [Results and incumbent-level receipts](recorded-math-validation-ties-results-v1.json)

## Source coverage

The authors' BBH and LMentry release covers 14 and 10 tasks, respectively. Earlier CPO archives already include almost the same roster. DOVE and PromptSuite require account consent to access their file contents. The ARC and AIME matrices supplied a usable comparison in two other task families. Both matrices had appeared in earlier CPO work. [Task inventory in the authors' paper](https://aclanthology.org/2024.tacl-1.52/) · [DOVE access](https://huggingface.co/datasets/nlphuji/DOVE_Lite) · [PromptSuite access](https://huggingface.co/datasets/eliyahabba/PromptSuite)

## Reproduce

Use pinned GEPA 0.1.4. The reduced score and cost snapshot supplies the replay data.

```sh
PYTHONHASHSEED=0 python -B -m benchmarks.recorded_math_validation_ties
PYTHONHASHSEED=0 python -B -m benchmarks.recorded_math_validation_ties \
  --execute b8b6e7ed7d0e5fa6371b54503b480c785743a24ea280a68cbbcea9cf8990ba1d \
  --out NEW_REPORT.json
```

Four focused tests passed and two replays matched byte for byte with sockets and DNS blocked. The proof tests cover strict-winner preservation, independent qualification, critical cases, and charged lookups. The CLI rejected a wrong seal and preserved an existing report when its path was supplied. Storage Guard measured 14.9 GiB free. The 14.9 MB replay overlay and partial source-download scratch were removed under the standing LAB exception. Historical ARC prices are sums over repeated replay splits. The replay incurred no model charges. [Focused tests](../tests/unit/test_recorded_math_validation_ties.py)
