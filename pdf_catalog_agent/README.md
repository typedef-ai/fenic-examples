# **📄 fenic Demo: PDF Processing, Analysis, and Content Discovery**

<p>
  <a href="https://colab.research.google.com/github/typedef-ai/fenic-examples/blob/main/pdf_catalog_agent/fenic_pdf_catalog_agent.ipynb">
    <img alt="Open in Colab" src="https://colab.research.google.com/assets/colab-badge.svg">
  </a>
</p>

Turn a folder of PDFs into a **queryable, agent-ready catalog**. This repo contains a Colab notebook that:

1. parses PDFs into section-scoped rows,  
2. saves two tidy Fenic tables, and  
3. exposes **three** minimal MCP tools for deterministic queries.

---

## **Why this exists**

Skimming raw PDFs doesn’t scale. Teams need a **curated index** they can query and wire into agents/UI without letting a model process over 80 pages.

This project keeps the surface area **optimal**:

* We normalize whitepapers into `whitepaper_sections` and `whitepaper_topics`.  
* We expose **three** MCP tools only:  
  * `list_whitepapers()`  
  * `sections_by_topic(topic)`  
  * `search_sections(query)`

That’s enough to power search, reviews, and agent flows with predictable outputs. You can also extend the tool catalog to search, if you want your agents or MCP clients to query the server with questions and retrieve content from your whitepapers with `qa_sections(question: str)` and `qa_sections_kw(kw1..kw6)` we suggested as next steps in the Colab notebook.

---

## **What you get**

### **1\) Tables (idempotent)**

* **`whitepaper_sections`**  
  * `id` – document id  
  * `name` – document name  
  * `heading` – H1/H2/H3 text  
  * `level` – 1|2|3  
  * `content` – section body text  
  * `full_path` – breadcrumb (e.g., `1. Overview > 1.2 Data Policy`)  
* **`whitepaper_topics`** (long format)  
  * `doc_id` – fk → sections.id  
  * `name` – document name  
  * `topic` – `"training" | "soc" | "governance"`  
  * `heading` – section heading aligned to that topic

We persist with `save_as_table(..., mode="overwrite")` so re-runs are clean.

### **2\) MCP tools (three)**

* `list_whitepapers()` → (`name`, `n_sections`)  
* `sections_by_topic(topic)` → curated rows joined by `(doc_id, heading)`  
* `search_sections(query)` → case-insensitive substring on `heading`/`content`

---

## **🚀 Quickstart**

### **1\) Environment**

```shell
# Python 3.10+ recommended
python -m venv .venv && source .venv/bin/activate  # (Windows: .venv\Scripts\activate)
pip install -r requirements.txt
# or, if you're installing manually:
pip install fenic fastmcp
```

### **2\) Run the notebook**

Open **`notebooks/fenic_pdf_classification.ipynb`** (or the shared Colab) and execute top-to-bottom:

1. **Load & extract sections** (H1–H3 from markdown/PDF).

2. **Build topics index** (`training`, `soc`, `governance`) from your light classification step.

3. **Persist tables**: `whitepaper_sections`, `whitepaper_topics`.

4. **Register MCP tools**: `list_whitepapers`, `sections_by_topic`, `search_sections`.

5. **Start MCP server** (HTTP) and note the printed `HOST:PORT`.

---

## **🛠️ MCP tools (stable, deterministic)**

### **1\) `list_whitepapers()`**

* **Params:** none

* **Returns:** `name`, `n_sections`

* **Use:** discover scope, quick sanity check

### **2\) `sections_by_topic(topic)`**

* **Params:** `topic` in `{ "training", "soc", "governance" }` (case-insensitive)

* **Returns:** curated slice of sections joined via `(doc_id, heading)`

* **Use:** produce shareable, reviewable packs (e.g., all governance sections)

### **3\) `search_sections(query)`**

* **Params:** `query` (string)

* **Returns:** sections with `heading` or `content` **ILIKE** `query`

* **Use:** fast ad-hoc lookups with provenance (heading \+ full\_path)

We intentionally keep tool plans to **built-ins** (filters, joins, projections). No UDFs or LLM calls in tool definitions → cleaner serialization, predictable results.

---

## **Design choices (and how to extend)**

* **Sections, not pages.** We extract H1/H2/H3 chunks so queries match how humans navigate documents.  
* **No UDFs in tool plans.** MCP tools serialize logical plans. Keep UDFs in your *prep* pipeline, not inside `create_tool` queries.  
* **Case-insensitive everywhere.** `ilike`/`text.lower` avoids easy misses.  
* **Small surface area.** Three tools tell a clear story and are easy to adopt.

**Optional upgrades (later):**

* **Vector similarity:** add `joined_text = heading + "\n\n" + content` and `joined_vec = semantic.embed(joined_text)`, then create a fourth `vector_sections(question, min_sim=0.35)` tool.  
* **LLM ranking (client-side):** if you need model-rated relevance, score the small candidate set **after** you call an MCP tool, don’t embed LLM calls inside tool definitions.

---

## **Troubleshooting**

* **`UDFExpr cannot be serialized` when creating a tool**  
  Remove UDFs from the tool query. Compute UDF-derived columns **before** saving tables; then build tools from built-ins (select/join/filter).  
* **Pydantic/validation errors when calling semantic ops**  
  Ensure semantic functions receive the expected types. For example, `semantic.map` expects string input for the prompt/instruction, not a Fenic Column. Compose strings with Fenic text functions (e.g., `fc.text.concat`) if needed during DataFrame prep.  
* **No tools listed/connection error**  
  Confirm the server cell printed the `✅ MCP HTTP server ready ...` line and that your smoke test uses that exact `HOST:PORT`.  
* **Empty search results**  
  Try a simpler `query` or verify that `whitepaper_sections` has non-empty `heading`/`content`. You can quickly `select(...).limit(5).collect()` in the notebook to inspect rows.

---

## **Security & privacy**

* The demo reads your local/Colab files and runs a local HTTP MCP server by default.  
* If you enable embeddings or other model calls, **review your provider’s data policies** and avoid sending sensitive content to external APIs.

---

## **FAQs**

**Q: Can I point this at my existing docs site?**  
 Yes. Convert HTML→markdown, preserve headings, then run the same section extraction step.

**Q: Do I need embeddings to get value?**  
 No. Substring search over clean sections \+ a curated topics index already covers a lot of queries. Add vectors later if you need ranked semantic matches.

**Q: Can I run this on a schedule?**  
 Yes. The pipeline is plain fenic DataFrame code. Wrap it in your job runner of choice (Airflow, cron, GitHub Actions, etc.).

---

## **License**

MIT (see `LICENSE` in the repo).

---

## **Acknowledgements**

Built with ❤️ using [**fenic**](https://docs.fenic.ai/latest/) (an opinionated, PySpark-inspired DataFrame framework for AI/agentic apps) and [**fastmcp**](https://pypi.org/project/fastmcp/) for quick client testing.