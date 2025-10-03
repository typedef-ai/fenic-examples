# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Hacker News agent built with Fenic - a PySpark-inspired DataFrame framework with semantic AI capabilities. The project demonstrates how to build production AI agents that combine structured data processing with LLM operations.

## Development Environment

### Package Manager
This project uses `uv` for dependency management. Always use `uv` commands for package operations:
- Install dependencies: `uv sync`
- Add packages: `uv add package-name`
- Run Python scripts: `uv run python script.py`
- Activate virtual environment: `source .venv/bin/activate`

### Key Dependencies
- `fenic[mcp]>=0.4.2` - Core framework with MCP support
- `pydantic-ai[mcp]>=1.0.10` - Pydantic AI with MCP integration
- `duckdb==1.3.0` - Local SQL engine for data operations

## Fenic Framework Patterns

### Session Creation
Always create a Fenic session with semantic configuration:
```python
from fenic.api.session import Session
from fenic.api.session.config import SessionConfig, SemanticConfig, OpenAILanguageModel

config = SessionConfig(
    app_name="hn_agent",
    db_path="./data/hn.db",  # Optional persistent storage
    semantic=SemanticConfig(
        language_models={
            "gpt4": OpenAILanguageModel(
                model_name="gpt-4o-mini",
                rpm=100,
                tpm=100_000
            )
        }
    )
)
session = Session.get_or_create(config)
```

### Import Conventions
Use these standard imports:
```python
import fenic.api.functions as fc
import fenic.api.functions.semantic as semantic
import fenic.api.functions.embedding as embedding
from fenic.api.column import col
from fenic.core.types.schema import Schema, ColumnField
from fenic.core.types.datatypes import StringType, IntegerType
```

### Data Loading Patterns

For HuggingFace datasets:
```python
df = session.read.parquet("hf://datasets/org/dataset-name@~parquet/**/*.parquet")
```

For local files:
```python
df = session.read.csv("data/*.csv", merge_schemas=True)
```

### Semantic Operations

Always use column references with `fc.col()`:
```python
# Correct
df.filter(semantic.predicate("This {text} is about Hacker News", text=fc.col("content")))

# Incorrect - don't use string column names in semantic operations
df.filter(semantic.predicate("This {text} is about HN", text="content"))
```

### Table Storage
Save DataFrames as persistent tables:
```python
df.write.save_as_table("hn_stories", mode="overwrite")
# Load later with:
df = session.table("hn_stories")
```

### MCP Tool Creation
Create parameterized tools for MCP servers:
```python
from fenic.core.mcp.types import ToolParam
from fenic.core.types.datatypes import StringType

filtered_df = df.filter(
    fc.col("title").contains(fc.tool_param("query", StringType))
)

session.catalog.create_tool(
    tool_name="search_hn",
    tool_description="Search Hacker News stories",
    tool_query=filtered_df,
    result_limit=10,
    tool_params=[ToolParam(name="query", description="Search query")]
)
```

## Code Architecture

### Directory Structure
- `src/` - Main source code
  - Agent implementations should go here
  - MCP server configurations
  - Data processing pipelines
- `assets/data/` - Local data files (currently empty)
- Project uses Fenic's lazy evaluation - build query plans first, execute only when needed

### Error Handling
Fenic operations that fail return None instead of raising exceptions for:
- Semantic operations with invalid inputs
- Async UDF failures
- Missing columns in lazy evaluation are caught at execution time

### Performance Considerations
- Use `merge_schemas=False` (default) for consistent schema files
- Batch semantic operations when possible
- Configure appropriate RPM/TPM limits for LLM providers
- Use `session.sql()` for complex joins instead of multiple DataFrame operations

## Environment Variables

Required for API access:
- `OPENAI_API_KEY` - For OpenAI models
- `ANTHROPIC_API_KEY` - For Anthropic models  
- `HF_TOKEN` - For private HuggingFace datasets

## Common Tasks

### Run MCP Server
```python
from fenic.api.mcp.server import create_mcp_server, run_mcp_server_sync

server = create_mcp_server(session, "hn_agent", tools=["search_hn"])
run_mcp_server_sync(server, transport="stdio")
```

### Query Metrics
```python
# View LLM usage and costs
metrics_df = session.table("fenic_system.query_metrics")
metrics_df.filter(fc.col("total_lm_cost") > 0).show()
```

## Comprehensive Fenic Reference

### DataFrame Operations

#### Basic Operations
```python
# Filter, select, group by - all lazy evaluated
df = df.filter(fc.col("score") > 100)
df = df.select(fc.col("title"), fc.col("score"))
df = df.group_by("author").agg(fc.count("*"), fc.avg("score"))
df = df.sort(fc.desc("score"))
df = df.distinct()
df = df.limit(100)

# Execute with actions
df.show()  # Display results
df.count()  # Get row count
df.to_polars()  # Convert to Polars DataFrame
df.to_pandas()  # Convert to Pandas DataFrame
```

#### Joins
```python
# Regular join
df1.join(df2, on=fc.col("id"), how="inner")  # inner, outer, left, right, cross

# Semantic join with natural language
df1.semantic.join(
    df2,
    predicate="The {left_on} describes the same person as {right_on}",
    left_on=fc.col("description"),
    right_on=fc.col("bio"),
    examples=examples  # Optional JoinExampleCollection
)

# Similarity join (top-k matches)
df1.semantic.sim_join(
    df2,
    left_on=semantic.embed(fc.col("text")),
    right_on=semantic.embed(fc.col("content")),
    k=5,
    similarity_metric="cosine",  # or "dot", "l2"
    similarity_score_column="score"
)
```

### Semantic Operations

#### Map - Transform text with LLM
```python
from fenic.core.types.semantic_examples import MapExample, MapExampleCollection

# Basic mapping
df = df.with_column(
    "summary",
    semantic.map(
        "Summarize this article: {{ content }}",
        content=fc.col("text"),
        temperature=0.7,
        max_output_tokens=200
    )
)

# With few-shot examples
examples = MapExampleCollection()
examples.create_example(MapExample(
    input={"text": "Long article..."},
    output="Short summary"
))

df = df.with_column(
    "summary",
    semantic.map(
        "Summarize: {{ text }}",
        text=fc.col("content"),
        examples=examples
    )
)

# Structured output with Pydantic
from pydantic import BaseModel, Field

class Summary(BaseModel):
    title: str = Field(description="Article title")
    key_points: list[str] = Field(description="Main points")

df = df.with_column(
    "structured_summary",
    semantic.map(
        "Extract information from: {{ text }}",
        text=fc.col("content"),
        response_format=Summary
    )
)
```

#### Predicate - Boolean filtering with LLM
```python
from fenic.core.types.semantic_examples import PredicateExample, PredicateExampleCollection

# Filter with natural language
df = df.filter(
    semantic.predicate(
        "This {{ text }} discusses artificial intelligence",
        text=fc.col("content")
    )
)

# With examples for consistency
examples = PredicateExampleCollection()
examples.create_example(PredicateExample(
    input={"text": "Machine learning models..."},
    output=True
))
examples.create_example(PredicateExample(
    input={"text": "Recipe for cake..."},
    output=False
))

df = df.filter(
    semantic.predicate(
        "This {{ text }} is about technology",
        text=fc.col("content"),
        examples=examples
    )
)
```

#### Extract - Structured extraction
```python
from typing import List, Optional

class Entity(BaseModel):
    name: str = Field(description="Entity name")
    type: str = Field(description="Entity type")

class ExtractedData(BaseModel):
    entities: List[Entity] = Field(description="Named entities")
    sentiment: str = Field(description="Sentiment: positive/negative/neutral")
    topics: List[str] = Field(description="Main topics")

df = df.with_column(
    "extracted",
    semantic.extract(fc.col("text"), ExtractedData)
)

# Access nested fields
df = df.select(
    fc.col("extracted.entities"),
    fc.col("extracted.sentiment")
)
```

### Embeddings

```python
# Generate embeddings
df = df.with_column(
    "embeddings",
    semantic.embed(fc.col("text"))
)

# Normalize embeddings
df = df.with_column(
    "norm_embeddings",
    embedding.normalize(fc.col("embeddings"))
)

# Compute similarity
df = df.with_column(
    "similarity_to_query",
    embedding.compute_similarity(
        fc.col("embeddings"),
        query_vector,  # List of floats or numpy array
        metric="cosine"  # or "dot", "l2"
    )
)

# Clustering with K-means
df = df.semantic.with_cluster_labels(
    by=semantic.embed(fc.col("text")),
    num_clusters=5,
    label_column="cluster",
    centroid_column="centroid"  # Optional
)
```

### Column Operations

```python
# Column creation and reference
fc.col("name")  # Reference column
fc.lit(42)  # Literal value

# Type casting
fc.col("id").cast(StringType)
fc.col("score").cast(DoubleType)

# Conditionals
fc.when(fc.col("score") > 100, fc.lit("high"))
  .when(fc.col("score") > 50, fc.lit("medium"))
  .otherwise(fc.lit("low"))

# String operations
fc.col("text").contains("keyword")
fc.text.lower(fc.col("name"))
fc.text.upper(fc.col("name"))
fc.text.split(fc.col("tags"), ",")
fc.text.concat(fc.col("first"), fc.lit(" "), fc.col("last"))
fc.text.regexp_replace(fc.col("text"), r"\d+", "X")

# JSON operations
fc.json.get(fc.col("data"), "$.field")
fc.json.contains(fc.col("data"), '{"key": "value"}')
```

### Advanced Session Configuration

```python
from fenic.api.session.config import (
    SessionConfig, SemanticConfig, CloudConfig,
    OpenAILanguageModel, AnthropicLanguageModel,
    OpenAIEmbeddingModel, ModelAlias
)

# Multiple models with profiles
config = SessionConfig(
    app_name="hn_agent",
    db_path="./data/hn.db",
    semantic=SemanticConfig(
        language_models={
            "gpt4": OpenAILanguageModel(
                model_name="gpt-4o-mini",
                rpm=100,
                tpm=100_000,
                profiles={
                    "fast": OpenAILanguageModel.Profile(reasoning_effort="low"),
                    "thorough": OpenAILanguageModel.Profile(reasoning_effort="high")
                },
                default_profile="fast"
            ),
            "claude": AnthropicLanguageModel(
                model_name="claude-3-5-haiku-latest",
                rpm=100,
                input_tpm=50_000,
                output_tpm=50_000
            )
        },
        default_language_model="gpt4",
        embedding_models={
            "openai": OpenAIEmbeddingModel(
                model_name="text-embedding-3-small",
                rpm=100,
                tpm=100_000
            )
        },
        default_embedding_model="openai"
    )
)

# Use specific model/profile in operations
df = df.with_column(
    "summary",
    semantic.map(
        "Summarize: {{ text }}",
        text=fc.col("content"),
        model_alias=ModelAlias(name="gpt4", profile="thorough")
    )
)
```

### Catalog Operations

```python
# Create catalog/database/table structure
session.catalog.create_catalog("my_catalog")
session.catalog.set_current_catalog("my_catalog")
session.catalog.create_database("my_database")
session.catalog.set_current_database("my_database")

# Create and manage tables
from fenic.core.types.schema import Schema, ColumnField
from fenic.core.types.datatypes import StringType, IntegerType

schema = Schema([
    ColumnField("id", IntegerType),
    ColumnField("title", StringType)
])
session.catalog.create_table("stories", schema, description="HN stories")

# List and describe tables
tables = session.catalog.list_tables()
metadata = session.catalog.describe_table("stories")
exists = session.catalog.does_table_exist("stories")

# Create views (virtual datasets)
df_filtered = df.filter(fc.col("score") > 100)
df_filtered.write.save_as_view("top_stories", description="High scoring stories")
```

### SQL Interface

```python
# Execute SQL on DataFrames
result = session.sql("""
    SELECT 
        author,
        COUNT(*) as post_count,
        AVG(score) as avg_score
    FROM {stories} s
    JOIN {comments} c ON s.id = c.story_id
    WHERE s.score > 100
    GROUP BY author
    ORDER BY avg_score DESC
""", stories=df_stories, comments=df_comments)
```

### Async UDFs for I/O Operations

```python
from fenic.api.functions.builtin import async_udf
import aiohttp

@async_udf(
    return_type=StructType([
        StructField("status", IntegerType),
        StructField("data", StringType)
    ]),
    max_concurrency=20,
    timeout_seconds=5,
    num_retries=2
)
async def fetch_api_data(id: str) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://api.example.com/{id}") as resp:
            return {
                "status": resp.status,
                "data": await resp.text()
            }

df = df.with_column("api_response", fetch_api_data(fc.col("id")))
```

### Window Functions

```python
from fenic.api.window import Window

# Ranking
df = df.with_column(
    "rank",
    fc.row_number().over(Window.partition_by("category").order_by(fc.desc("score")))
)

# Moving averages
df = df.with_column(
    "moving_avg",
    fc.avg("score").over(
        Window.partition_by("author")
              .order_by("timestamp")
              .rows_between(-5, 0)  # Last 5 rows including current
    )
)
```

### Data Writing

```python
# Write to files
df.write.csv("output.csv", mode="overwrite")
df.write.parquet("output.parquet", mode="overwrite")

# Write to S3
df.write.parquet("s3://bucket/path/data.parquet")

# Append to existing table
df.write.save_as_table("stories", mode="append")
```

### Important Notes

1. **Lazy Evaluation**: DataFrames are lazy - operations build a query plan that only executes with actions like `show()`, `count()`, or `to_polars()`

2. **Column References**: Always use `fc.col()` in semantic operations, never string column names

3. **None Handling**: Set `strict=True` (default) in semantic ops to skip rows with None values

4. **Rate Limiting**: Configure appropriate RPM/TPM for each model to avoid throttling

5. **Examples**: Use example collections to improve consistency in semantic operations

6. **Schema Types**: 
   - Primitives: StringType, IntegerType, FloatType, DoubleType, BooleanType
   - Complex: ArrayType, StructType, EmbeddingType, MarkdownType, JsonType

7. **Error Handling**: Semantic operations return None on failure rather than raising exceptions