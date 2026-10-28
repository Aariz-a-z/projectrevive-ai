# Recommendation quality evaluation

```bash
cd backend
./.venv/Scripts/python.exe -m eval.run_eval          # Windows
python -m eval.run_eval                              # macOS/Linux
```

Costs nothing and touches no network.

## Headline result: the hybrid does not win outright

Measured on 2026-10-28, 10 cases, 22 knowledge base entries, TF-IDF embedder:

| system | P@3 | NDCG@3 | P@5 | NDCG@5 | P@10 | NDCG@10 | Recall@10 | Coverage@10 | Items |
|---|---|---|---|---|---|---|---|---|---|
| hybrid | 0.700 | 0.736 | 0.520 | 0.679 | **0.420** | **0.742** | **0.699** | **1.000** | 8.9 |
| rules-only | **0.733** | **0.746** | **0.600** | **0.726** | 0.370 | 0.738 | 0.628 | **1.000** | 5.9 |
| content-only | 0.300 | 0.197 | 0.280 | 0.223 | 0.260 | 0.323 | 0.445 | 0.864 | 8.1 |

**The rules-only baseline beats the hybrid at the top of the ranking** — at
P@3, NDCG@3, P@5 and NDCG@5. The hybrid leads only at K=10 and on recall.

That is reported here rather than tuned away. README section 8 asks for the
results honestly "including cases where the hybrid approach does not improve
performance", and this is one.

### What it means

Knowledge linkage is doing the work. When a rule detects a problem and an
entry declares it fixes that exact rule, the match is strong and precise.
Mixing content similarity into the score promotes loosely-related entries into
the top few slots, which costs precision exactly where it matters most — most
users read the first three recommendations, not the tenth.

Content similarity still earns its place: it is why the hybrid finds more of
the relevant items at all (Recall@10 0.699 against 0.628). The honest summary
is **content similarity trades top-of-list precision for coverage**, and on
this evaluation set that trade is currently not worth it at K=3.

### Read the P@10 column carefully

Precision divides by K, so a system returning 5.9 items on average cannot
exceed 0.59 at P@10 no matter how well it ranks. Rules-only only produces
recommendations for entries linked to a detected finding, so it runs out.
**The hybrid's P@10 lead is substantially a list-length artifact, not better
ranking.** The runner prints this caveat with the results for the same reason
it is here. The Recall@10 difference is a real gain; the P@10 difference
mostly is not.

### Why the weights were not tuned until the hybrid won

With 10 cases there is no honest train/test split, so tuning the weights
against this set and then reporting the improved number would be fitting the
evaluation and reporting the fit as a result. The weights in
`app/schemas/recommendation.py` are the hand-chosen starting values that were
set before this was measured, and they stay that way until there is enough
labelled data to hold some back.

## Method

Each case gives a project description, the findings a reviewer would expect,
and graded relevance for knowledge base entries:

| grade | meaning |
|---|---|
| 3 | clearly the right advice for this project |
| 2 | useful and appropriate |
| 1 | marginal; not wrong, but not a priority here |
| 0 | irrelevant or unsuitable (also the default for anything unlisted) |

Binary metrics count grade ≥ 2 as relevant. NDCG uses the full grade, so
putting the single best item first scores above merely putting a relevant item
first.

Cases supply profiles directly rather than documents to extract, so what is
measured is the recommender alone. A regression in extraction should not look
like a regression in ranking.

The three systems are the hybrid and the two ablations: knowledge linkage with
no text similarity, and text similarity with no findings. Both are the real
implementations in `app/recommend/baselines.py`, not strawmen.

## Limitations

These matter more than the numbers.

- **10 cases.** One case moving a few places visibly shifts every mean. Treat
  differences under about 0.05 as noise.
- **One annotator, who also wrote the knowledge base being scored.** The
  labels and the system share assumptions, so every number here is biased
  upward. This is the single largest caveat and it cannot be fixed by adding
  cases — it needs a different annotator.
- **No inter-annotator agreement**, because there is no second annotator.
- **Relevance is appropriateness, not outcome.** No recommendation here has
  been implemented on a real project and measured. Nothing in this table is
  evidence that following the advice improves anything.
- **No statistical testing.** At this sample size a significance test would be
  theatre.

## Extending it

Add cases to `dataset/cases.yaml`. The tests in
`tests/test_eval_dataset.py` enforce the consistency that silently corrupts
results otherwise: judged ids must exist in the knowledge base (a typo would
become an invisible grade-0 label), referenced rules must exist, and each case
needs both relevant and irrelevant items or precision cannot discriminate on
it. That last check found a real flaw in a case written here.

The most valuable contribution is not more cases from the same person. It is
ten cases labelled by somebody else.
