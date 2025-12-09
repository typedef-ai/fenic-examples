# **AI Feature Engineering with fenic**

<p>
  <a href="https://colab.research.google.com/github/typedef-ai/fenic-examples/blob/main/ai_feature_engineering/fenic_ai_feature_engineering.ipynb">
    <img alt="Open in Colab" src="https://colab.research.google.com/assets/colab-badge.svg">
  </a>
</p>

End-to-end demo that takes a small web article corpus (e.g. Medium/TDS posts), turns it into a **semantic feature table** with **clusters**, **narrative intent labels**, and **complexity buckets** using [**fenic**](https://docs.fenic.ai/). fenic an opinionated, PySpark-inspired DataFrame framework for AI/agentic applications.

The goal: give editors, PMs, and agent builders a *clean, columnar view* of the content they already have, without leaving the DataFrame world.

---

## **Overview**

**What this demo does**

* **Ingest & clean:** load a small CSV of articles (URL, title, body) into a fenic DataFrame.

* **Text features:** derive `body_clip`, character lengths, and simple “has code?” flags.

* **Embeddings & clusters:** embed article clips and assign each row to a semantic cluster.

* **Cluster summaries:** use `semantic.extract` to generate short, grounded summaries per cluster.

* **Narrative intent labeling:** few-shot `semantic.classify` to tag each article as:  
   `news/announcement`, `tutorial/how-to`, `opinion/thinkpiece`, `research/explainer`, or `case-study/showcase`.

* **Complexity buckets:** assign each article a `beginner | intermediate | advanced` label based on length and presence of code.

* **Artifacts:** write out parquet and CSV files ready for further use:

  * `features.parquet` and `features.csv` : one row per article, feature-rich.

  * `cluster_report.csv` : one row per cluster, with exemplars and summaries.

Everything is done **natively in fenic** (no Pandas or ad-hoc Python loops) so it’s easy to port this pipeline into production.

---

## Quickstart

### **1\) Install**

```bash
!pip -q install fenic datasets python-dotenv
# (optional) providers you plan to use, e.g.:
# pip install -U openai
```
If you’re running in Colab, the notebook includes the install cell; you can just run it.

### **2\) Configure models**

This demo uses two model aliases configured via fenic’s semantic config in **Step 1** of the notebook:

* `mini` – for `semantic.extract` and `semantic.classify` (e.g. an LLM like `gpt-4o-mini` or similar).

* `embed` – for `semantic.embed` (e.g. an embedding model).

You’ll typically set your provider API key(s) as environment variables before running the notebook, for example:

```shell
export OPENAI_API_KEY="sk-..."
```

The notebook shows exactly how these aliases are wired into fenic’s `semantic_cfg`.

### **3\) Run the demo**

Open the notebook in Colab (badge above) and run the cells top-to-bottom.

What happens, step by step:

1. **Config & setup**

   * Imports fenic and sets up a `Session` with semantic config (`mini`, `embed`).

   * Ensures all output goes under a configurable `OUT_DIR` (default: `/content/out`).

2. **Ingest & basic cleaning**

   * Reads a small CSV of articles into a fenic DataFrame: `url`, `title`, `body`.

   * Derives a trimmed `body_clip` field to keep prompts token-friendly.

   * Adds simple metrics like `char_len` and `clip_len`.

3. **Feature engineering (fenic-only transforms)**

   * Adds a boolean `has_code` flag using regex over `body_clip`.

   * Builds a `complexity_bucket` column combining length and `has_code` (e.g. short & no code → `beginner`).

4. **Embeddings & clustering**

   * Calls `semantic.embed` over a compact, enriched text field (built from title/body).

   * Calls fenic’s clustering helper to assign each row to a `cluster` plus a human-readable `cluster_label`.

   * Picks an exemplar article per cluster (closest to centroid).

5. **Narrative intent classification**

   * Uses `semantic.classify` with a small few-shot example set to label each article’s `intent`:  
      `news/announcement`, `tutorial/how-to`, `opinion/thinkpiece`, `research/explainer`, `case-study/showcase`.

   * Keeps cost low by classifying only up to a configurable max number of rows (e.g. 300).

6. **Cluster report generation**

   * Joins exemplar rows with counts and cluster labels.

   * Uses `semantic.extract` with a tiny Pydantic schema to generate **grounded summaries** per cluster (1–3 bullets).

   * Produces `cluster_report.csv` with:

     * `cluster`, `cluster_label`, `count`

     * `exemplar_title`, `exemplar_url`, `exemplar_dist`

     * `cluster_summary` (human-readable bullet string)

     * optional `cluster_key_terms`.

7. **Final feature table**

   * Builds `features.csv` as a flat feature table per article:

     * Identification: `url`, `title`, `body_clip`

     * Text metrics: `char_len`, `clip_len`

     * Features: `has_code`, `complexity_bucket`, `intent`

     * Clustering: `cluster`, `cluster_label`

   * Writes it via fenic’s native `write.csv`.

At the end, you’re left with two artifacts you can drop straight into downstream workflows (dashboards, agents, or offline analysis).

---

## **Artifacts**

By default, the notebook writes outputs to:

```
/content/out/
  features.csv
  features.parquet         # one row per article
  cluster_report.csv   # one row per cluster
```

You can change `OUT_DIR` near the top of the notebook if you want them elsewhere.

### **`features.csv` and `features.parquet` (per-article view)**

Typical columns:

* `url` – canonical article URL.

* `title` – article title.

* `body_clip` – token-friendly text snippet used for models.

* `char_len`, `clip_len` – rough size measures.

* `has_code` – heuristic flag if the article contains code.

* `complexity_bucket` – `beginner | intermediate | advanced`.

* `intent` – high-level narrative type (`news/announcement`, `tutorial/how-to`, etc.).

* `cluster`, `cluster_label` – cluster ID and human-readable label.

### **`cluster_report.csv` (per-cluster view)**

Typical columns:

* `cluster` – integer cluster ID.

* `cluster_label` – label derived during clustering / summarization.

* `count` – number of articles in the cluster.

* `exemplar_title`, `exemplar_url` – representative article.

* `exemplar_dist` – distance to cluster centroid (smaller \= more central).

* `cluster_summary` – 1–3 bullet-style phrases describing the cluster.

* `cluster_key_terms` – optional comma-separated terms.  

---

## Notebook Commands of Interest

> These are illustrative; the notebook contains the exact cells.

**Derive simple features**

````python
df = df.with_columns(
    fc.text.length("body_clip").alias("char_len"),
    (fc.text.regexp_count("body_clip", r"```|(^|\s)def\s|(^|\s)class\s|::") > fc.lit(0)).alias("has_code"),
)

df = df.with_columns(
    fc.when( (fc.col("char_len") < fc.lit(2500)) & (fc.col("has_code") == fc.lit(False)) )
      .then(fc.lit("beginner"))
      .when( (fc.col("char_len") < fc.lit(6000)) & (fc.col("has_code") == fc.lit(True)) )
      .then(fc.lit("intermediate"))
      .otherwise(fc.lit("advanced"))
      .alias("complexity_bucket")
)
````

**Few-shot examples (from your own corpus)**

```python
from fenic.api.semantic import ClassifyExample, ClassifyExampleCollection

def pick_examples(df_src, label, pattern):
    return (
        df_src
        .filter(fc.text.contains_regex("title", pattern, flags="i"))
        .select(
            fc.col("body_clip").alias("input"),
            fc.lit(label).alias("output")
        )
        .limit(2)
    )

examples_df = (
    pick_examples(df_src, "news/announcement", r"(announce|launch|series [abc]|funding)")
      .union(pick_examples(df_src, "tutorial/how-to", r"(how to|step[- ]by[- ]step|tutorial|guide)"))
      .union(pick_examples(df_src, "opinion/thinkpiece", r"(^why\s|opinion|thoughts|my take)"))
      .union(pick_examples(df_src, "research/explainer", r"(attention|transformer|explained|primer)"))
      .union(pick_examples(df_src, "case-study/showcase", r"(case study|postmortem|how .* reduced|cut .*%)"))
)

examples = ClassifyExampleCollection.from_rows(
    inputs=examples_df.select("input").to_list_flat(),
    outputs=examples_df.select("output").to_list_flat()
)
```

**Intent labeling**

```python
df_intent = df_src.select(
    "*",
    fc.semantic.classify(
        "body_clip",
        INTENT_CLASSES,
        examples=examples,
        model_alias="mini",
        temperature=0
    ).alias("intent")
)
```

**Embed + cluster + exemplar**

```python
df_emb = df_intent.select(
    "*",
    fc.semantic.embed(
        fc.text.concat_ws(" ", "[title:]", "title", "[clip:]", "body_clip"),
        model_alias="embed"
    ).alias("emb")
)

df_labeled = df_emb.with_cluster_labels("emb", k=10).select("*")  # cluster, cluster_label

exemplars = (
    df_labeled
    .with_columns((fc.lit(1.0) - fc.embedding.compute_similarity("emb", "centroid", metric="cosine"))
                  .alias("dist_to_centroid"))
    .sort(["cluster", "dist_to_centroid", "title"], ascending=[True, True, True])
    .group_by("cluster")
    .agg(
        fc.first("title").alias("exemplar_title"),
        fc.first("url").alias("exemplar_url"),
        fc.first("dist_to_centroid").alias("exemplar_dist"),
        fc.first("body_clip").alias("exemplar_body"),
    )
)
```

**Grounded bullets (Pydantic schema) → CSV-safe**

```python
from pydantic import BaseModel, Field
from typing import List

class ClusterBrief(BaseModel):
    summary: List[str] = Field(default_factory=list)

GUIDE = (
    "Summarize this exemplar with 1–3 short bullets (<=30 words each). "
    "Be concrete; mention likely audience and tone."
)

report_ctx = (
    exemplars.join(
        df_labeled.group_by("cluster").agg(fc.count("*").alias("count")),
        on="cluster", how="inner"
    )
    .select(
        "cluster", "count", "exemplar_title", "exemplar_url", "exemplar_dist", "exemplar_body",
        fc.text.concat_ws("\n",
            "== TASK ==", GUIDE,
            "== EXEMPLAR TITLE ==", "exemplar_title",
            "== BODY CLIP ==", "exemplar_body"
        ).alias("guided_text")
    )
)

brief = fc.semantic.extract("guided_text", ClusterBrief).alias("brief")

cluster_report = (
    report_ctx
    .select(
        "cluster", "count", "exemplar_title", "exemplar_url", "exemplar_dist",
        fc.text.array_join(brief["summary"], " • ").alias("cluster_summary")
    )
)
```

**Write artifacts (fenic only)**

```python
OUT_DIR = "/content/out"
(
  df_intent.select("url","title","body_clip","char_len","has_code","complexity_bucket","intent")
           .write.csv(f"{OUT_DIR}/features.csv")
)

(
  cluster_report.select("cluster","exemplar_title","exemplar_url","exemplar_dist","count","cluster_summary")
                .write.csv(f"{OUT_DIR}/cluster_report.csv")
)
```

---

## Outputs

* `out/features.csv` – per-article features + intent + (optional) cluster fields if joined.
* `out/cluster_report.csv` – per-cluster summary with exemplar and human-readable bullet string.

You can drop these into Sheets, dashboards, or a data lake as-is.

---

## Usage Examples

**Top clusters by size**

```python
fc.read.csv("out/cluster_report.csv").select("*").sort("count", ascending=False).show(10)
```

**Filter articles by intent and complexity**

```python
fc.read.csv("out/features.csv").filter(
    (fc.col("intent") == fc.lit("tutorial/how-to")) &
    (fc.col("complexity_bucket") == fc.lit("intermediate"))
).select("title","url").show(15)
```

---

## **Troubleshooting**

* **“semantic model alias not found”**  
   Make sure the semantic config cell (Step 1\) ran, and that you set environment variables (e.g. `OPENAI_API_KEY`) before embedding/extracting.

* **Rate limits / model errors**  
   Reduce the row caps for embedding/classification, or try a lighter model for `mini` / `embed`.

* **CSV is empty or missing columns**  
   Ensure you ran all cells, especially the ones that build `df_intent`, `df_labeled`, and the final feature table. The export cell assumes those exist.

* **Token limits with large bodies**  
   The pipeline intentionally uses `body_clip` (trimmed text) for model calls. If you change that, keep model limits in mind.

---

## **Repo Layout**

```text
ai_feature_engineering/
  README.md
  fenic_ai_feature_engineering.ipynb
  out/
    features.csv
    features.parquet
    cluster_report.csv
```

---

## License

MIT (see `LICENSE` in the repo).
---

**Credits**: Built with ❤️ by Typedef using [**fenic**](https://docs.fenic.ai/) — an opinionated, PySpark-inspired DataFrame framework with first-class semantic operators for AI/agentic apps.
