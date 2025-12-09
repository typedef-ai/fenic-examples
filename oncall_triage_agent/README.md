# fenic On-Call Triage Agent (LangChain/LangGraph)

<p>
  <a href="https://colab.research.google.com/github/typedef-ai/fenic-examples/blob/main/oncall_triage_agent/fenic_oncall_triage_agent.ipynb">
    <img alt="Open in Colab" src="https://colab.research.google.com/assets/colab-badge.svg">
  </a>
</p>

End-to-end demo that turns raw logs into actionable incident clusters with **fenic** (templates, semantic extraction, embeddings, k-means), exposes results via an **MCP** endpoint, and lets a **LangGraph / LangChain agent** answer natural-language questions over those MCP tools.

---

## Overview

**What it does**

- **Parse without regex:** multi-format log parsing via fenic templates (`text.extract` \+ `unnest`).  
- **Stable fingerprints:** LLM-assisted `semantic.extract` yields consistent grouping keys.  
- **Severity tagging:** rule-first, auditable `info | warn | error` with sortable scores.  
- **Clustering:** fenic’s native k-means over embeddings (`semantic.embed` \+ `with_cluster_labels`).  
- **Artifacts:** CSV/JSON/Markdown summaries.  
- **MCP tools:** `list_clusters`, `clusters_by_severity`, `assignments_for_cluster`, `coverage_metrics`.  
- **LangGraph agent:** ask “Which clusters matter?” or “Show assignments for \#5” and get an answer.

---

## Quickstart

### 1\) Install

```shell
# core
pip install -U fenic langgraph langchain-openai fastmcp

# optional: uv workflow
# uv sync
```

### 2\) Configure models 

```
export OPENAI_API_KEY="sk-..."
```

In Step 1 of the notebook/script we register:

* `mini` for `semantic.extract` (e.g., `gpt-4o-mini`)  
* `embed` for `semantic.embed` (e.g., `text-embedding-3-small`)

### 3\) Run the demo

You can open the notebook in Colab.

**What it does:**

1. Step 2 – Ingest: loads 10 sample entries into a fenic DF (source\_path, lineno, text).  
2. Step 3 – Parse: template-based extraction \+ unnest → timestamp, level, service, message, trace\_id.  
3. Step 4 – Fingerprint: semantic.extract → symbol, file, function, stem → human-readable fingerprint.  
4. Step 5 – Severity: rule-first tagging → severity, severity\_score.  
5. Step 6 – Cluster: embeddings \+ fenic k-means → cluster labels & exemplar summaries.  
6. Step 7 – Artifacts: CSV/JSON/Markdown, coverage.  
7. MCP appendix: exposes read-only tools over the computed tables.  
8. LangGraph agent: natural-language queries routed to the fenic MCP tools.

## MCP Tools (served in-notebook)

Once the “MCP appendix” cell runs, it:

* Saves `triage`, `clusters`, `assignments` to the fenic catalog.  
* Serves HTTP MCP at `http://127.0.0.1):<PORT>/mcp` with tools:

| Tool | Args | Returns |
| ----- | ----- | ----- |
| `list_clusters` | \`severity\_floor=info | warn |
| `clusters_by_severity` | \`severity=info | warn |
| `assignments_for_cluster` | `cluster_id: int` | Raw line assignments for that cluster |
| `coverage_metrics` | – | `processed_lines / total_lines` summary |

## Ask the Agent (LangGraph)

The notebook builds a small ReAct agent over those tools:

```py
await app("show top clusters at or above warn") 
await app("only error clusters") 
await app("what is our coverage?") 
await app("show assignments for cluster 5")
```

**Expected**: a clean Markdown table (long stack traces truncated) or a 1-row coverage summary.

## **Pipeline Details**

### **Step 2: Ingest**

* Deterministic assembly of `source_path, lineno, text`.

* Multi-line entries already grouped (stack traces kept intact).

### **Step 3: Parse (templates \+ `unnest`)**

* Three templates cover ISO, syslog-ish, and Python logging formats.

* `text.extract(...).alias("p1"|"p2"|"p3"|"tid")` → `unnest` → lift fields.

* `coalesce` picks the best match per field across formats.

### **Step 4: Fingerprint (LLM-assisted)**

* `semantic.extract` with a Pydantic schema (`symbol`, `file`, `function`, `stem`).

* Final fingerprint: `[service] | [symbol] | [file#function] | [stem]`.

### **Step 5: Severity (rule-first)**

* Lowercased variants (`msg_lc`, `level_norm`, `svc_lc`).

* Digit-safe checks for HTTP **5xx**, nginx upstream issues, timeouts, unique-constraint, etc.

* Adds `severity_score` for sorting.

### **Step 6: Clustering**

* `semantic.embed` text: `[svc][sev] message`.

* `semantic.with_cluster_labels` (k-means) per severity bin.

* Exemplar \= min distance to centroid; `summary` \= “SEV · N events · e.g. sample”.

### **Step 7: Artifacts**

* `out/clusters.csv`, `out/assignments.csv`, `out/clusters.json`, `out/assignments.json`, `out/report.md`.

* Coverage line in the README-style report, plus a compact daily summary string.

## **Usage Examples**

**List important clusters**

```py
await app("show top clusters at or above warn")
```

**Only ERROR clusters**

```py
await app("only error clusters")
```

**Coverage**

```py
await app("what is our coverage?")
```

**Assignments for a cluster**

```py
await app("show assignments for cluster 5")
```

## **Troubleshooting**

* **“No tools available”**: ensure the MCP server cell ran and registered tools.

* **Model alias error**: confirm Step 1 registers `mini` and `embed`.

* **Markdown table looks messy**: the helper trims whitespace and truncates long cells; keep summaries conservative.

* **LangGraph prompt arg change**: current code uses `create_react_agent(..., prompt=...)`. If the API changes, adjust accordingly.

## **Repo Layout**

```c#
oncall_triage_agent/
  README.md
  fenic_oncall_triage_agent.ipynb
  out/
    clusters.csv
    assignments.csv
    clusters.json
    assignments.json
    report.md
```

---

## **License**

MIT (see `LICENSE` in the repo)
