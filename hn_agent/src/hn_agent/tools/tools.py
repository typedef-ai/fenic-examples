"""
MCP tool registration for Hacker News data.
"""

import sys
from pathlib import Path
from typing import Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fenic.api.session import Session
import fenic.api.functions as fc
import fenic.api.functions.semantic as semantic
from fenic.core.types.datatypes import (
    StringType, BooleanType, IntegerType,
    ArrayType, StructField, StructType
)
from fenic.core.mcp.types import ToolParam

from hn_agent.session import get_session
from hn_agent.tools.models import DiscussionTheme, StorySummary


def register_story_search_tool(
    session: Session,
    tool_name: str = "search_stories",
    result_limit: int = 100,
) -> None:
    """Register a regex-based HN story search tool.
    
    Searches across story fields (title, URL, text) and all comments,
    tracing comments back to their root stories.
    
    Examples:
        Search for recent AI/ML discussions:
            pattern: "(?i)(artificial intelligence|machine learning|\\bAI\\b|\\bML\\b)"
            sort_order: "desc"
            
        Search for oldest Python posts:
            pattern: "(?i)python"
            sort_order: "asc"
            
        Find posts about specific companies:
            pattern: "(?i)(OpenAI|Anthropic|Google|Meta)"
            sort_order: "desc"
    
    Results are ranked by relevance, then sorted by date:
        1. Title matches (most relevant)
        2. URL matches
        3. Story text matches
        4. Comment matches
    """
    catalog = session.catalog
    
    # Drop existing tool if it exists
    try:
        catalog.drop_tool(tool_name)
    except:
        pass  # Tool doesn't exist, continue
    
    # Get tables
    items = session.table("items").filter(fc.col("type") == fc.lit("story"))
    comments = session.table("comments")
    
    # Tool parameters
    pattern = fc.tool_param("pattern", StringType)
    
    # Story-side matches
    title_match = fc.coalesce(fc.col("title"), fc.lit("")).rlike(pattern)
    url_match = fc.coalesce(fc.col("url"), fc.lit("")).rlike(pattern)
    story_text_match = fc.coalesce(fc.col("text"), fc.lit("")).rlike(pattern)
    
    story_hits = (
        items.with_column("title_match", title_match)
        .with_column("url_match", url_match)
        .with_column("text_match", story_text_match)
        .with_column(
            "match_rank",
            fc.when(fc.col("title_match"), fc.lit(1))
            .when(fc.col("url_match"), fc.lit(2))
            .when(fc.col("text_match"), fc.lit(3))
            .otherwise(fc.lit(999)),
        )
        .filter(fc.col("title_match") | fc.col("url_match") | fc.col("text_match"))
        .select(
            fc.col("id").alias("story_id"),
            fc.col("title"),
            fc.col("by").alias("author"),
            fc.col("time").alias("published_at"),
            fc.col("score"),
            fc.col("descendants").alias("comment_count"),
            fc.col("url"),
            fc.col("match_rank"),
        )
    )
    
    # Comment-side matches - always included but LIMIT to prevent memory explosion
    comment_text_match = fc.coalesce(fc.col("text"), fc.lit("")).rlike(pattern)
    matched_comments = (
        comments
        .filter(comment_text_match)
        .select(fc.col("id"), fc.col("parent").alias("parent_id"))
        .limit(5000)  # Limit matched comments to prevent memory issues
    )
    
    # Recursive SQL to trace comments back to root stories with depth limit
    comment_to_story_sql = """
        WITH RECURSIVE up(comment_id, parent_id, depth) AS (
            SELECT id, parent_id, 0 FROM {matched}
            UNION ALL
            SELECT up.comment_id, c.parent, up.depth + 1
            FROM up
            JOIN {all_comments} AS c ON c.id = up.parent_id
            WHERE up.parent_id IS NOT NULL
              AND up.depth < 20  -- Max depth to prevent runaway recursion
        )
        SELECT DISTINCT s.id AS story_id
        FROM up
        JOIN {stories} AS s ON up.parent_id = s.id
    """
    
    comment_stories = session.sql(
        comment_to_story_sql,
        matched=matched_comments,
        all_comments=comments,
        stories=items,
    )
    
    comment_hits = (
        items.join(comment_stories, left_on=fc.col("id"), right_on=fc.col("story_id"))
        .select(
            fc.col("id").alias("story_id"),
            fc.col("title"),
            fc.col("by").alias("author"),
            fc.col("time").alias("published_at"),
            fc.col("score"),
            fc.col("descendants").alias("comment_count"),
            fc.col("url"),
            fc.lit(4).alias("match_rank"),
        )
        .drop_duplicates(["story_id"])
    )
    
    # Combine results and apply dynamic sorting
    unified = (
        story_hits.union(comment_hits)
        .drop_duplicates(["story_id"])  # Ensure unique stories
    )
    
    # Sort by match_rank and published_at
    # For now, we'll use descending order for published_at (newest first)
    # The sort_order parameter can be handled in a future iteration
    sorted_results = unified.sort([fc.col("match_rank"), fc.col("published_at").desc()])
    
    # Final projection
    projection = sorted_results.select(
        fc.col("story_id").alias("id"),
        fc.col("title"),
        fc.col("author"),
        fc.col("published_at"),
        fc.col("score"),
        fc.col("comment_count"),
        fc.col("url"),
        fc.col("match_rank"),
    )
    
    # Tool parameters with detailed descriptions
    tool_params = [
        ToolParam(
            name="pattern",
            description=(
                "Regular expression pattern to search for. "
                "Examples: '(?i)python' for case-insensitive Python mentions, "
                "'\\b(AI|ML)\\b' for AI or ML as whole words, "
                "'OpenAI|Anthropic' for company names."
            ),
        ),
    ]
    
    # Register the tool
    catalog.create_tool(
        tool_name=tool_name,
        tool_description=(
            "Search Hacker News stories using regex patterns across titles, URLs, "
            "story text, and all related comments. Returns stories ranked by relevance "
            "(title > URL > text > comments) and sorted by date. Always searches comments "
            "to find all relevant discussions. Useful for finding conversations about "
            "specific topics, technologies, companies, or keywords."
        ),
        tool_query=projection,
        tool_params=tool_params,
        result_limit=result_limit,
        ignore_if_exists=False,
    )
    
    print(f"✓ Registered tool: {tool_name}")


def register_read_story_tool(
    session: Session,
    tool_name: str = "read_story",
    result_limit: int = 2000,  # Reduced from 5000
) -> None:
    """Register a tool that returns a story with optional comment thread.
    
    Fetches a complete Hacker News story with its entire comment thread.
    Returns one row per comment/story, maintaining hierarchical structure
    via depth and path columns. The path column uses zero-padded IDs
    (e.g., "0000012345.0000012346") to maintain thread ordering.
    
    Examples:
        Get just story metadata:
            story_id: 12345
            include_comments: false
            
        Get full discussion thread:
            story_id: 12345
            include_comments: true
    """
    
    catalog = session.catalog
    
    # Drop existing tool if it exists
    try:
        catalog.drop_tool(tool_name)
    except:
        pass  # Tool doesn't exist, continue
    
    # Data sources (removed typedef_default prefix)
    items = session.table("items").filter(fc.col("type") == fc.lit("story"))
    comments = session.table("comments")
    users = session.table("users")
    
    # Tool parameters
    story_id = fc.tool_param("story_id", IntegerType)
    # Note: include_comments parameter removed as it can't be used in SQL directly
    
    # Root story selection (parameterized)
    root = items.filter(fc.col("id") == story_id)
    
    # SQL to get story and all comments with depth limit
    sql = """
        WITH RECURSIVE thread AS (
            -- Get the story itself
            SELECT
                i.id,
                i.parent,
                0 AS depth,
                lpad(CAST(i.id AS VARCHAR), 10, '0') AS path,
                i.title,
                i.url,
                i.text,
                i.by,
                i.score,
                i.time,
                TIMESTAMP '1970-01-01' + CAST(i.time AS BIGINT) * INTERVAL 1 SECOND AS ts,
                i.type
            FROM {items} AS i
            WHERE i.id IN (SELECT id FROM {root})

            UNION ALL

            -- Recursively get comments up to depth 10
            SELECT
                c.id,
                c.parent,
                t.depth + 1,
                t.path || '.' || lpad(CAST(c.id AS VARCHAR), 10, '0') AS path,
                c.title,
                c.url,
                c.text,
                c.by,
                c.score,
                c.time,
                TIMESTAMP '1970-01-01' + CAST(c.time AS BIGINT) * INTERVAL 1 SECOND AS ts,
                c.type
            FROM {comments} AS c
            JOIN thread AS t ON c.parent = t.id
            WHERE t.depth < 10  -- Limit recursion depth
        ),
        meta AS (
            SELECT
                i.id AS story_id,
                i.title,
                i.by AS story_by,
                i.url,
                regexp_extract(i.url, '^(?:https?://)?(?:www\\.)?([^/]+)', 1) AS domain,
                TIMESTAMP '1970-01-01' + CAST(i.time AS BIGINT) * INTERVAL 1 SECOND AS published_at,
                i.score,
                i.descendants,
                (i.text IS NOT NULL) AS has_text,
                length(coalesce(i.text, '')) AS text_length,
                u.karma AS author_karma,
                TIMESTAMP '1970-01-01' + CAST(u.created AS BIGINT) * INTERVAL 1 SECOND AS author_created_at
            FROM {root} AS i
            LEFT JOIN {users} AS u ON u.id = i.by
        ),
        stats AS (
            SELECT
                COUNT(*) FILTER (WHERE type = 'comment') AS comments_count,
                COUNT(DISTINCT by) FILTER (WHERE type = 'comment') AS unique_commenters_count,
                MAX(depth) FILTER (WHERE type = 'comment') AS max_depth
            FROM thread
        )
        SELECT
            m.story_id,
            m.title,
            m.story_by,
            m.published_at,
            m.url,
            m.domain,
            m.score,
            m.author_karma,
            m.author_created_at,
            m.has_text,
            m.text_length,
            s.comments_count,
            s.unique_commenters_count,
            COALESCE(s.max_depth, 0) AS max_depth,
            t.id AS node_id,
            t.parent,
            t.depth,
            t.path,
            t.by AS node_by,
            t.ts AS node_ts,
            t.score AS node_score,
            t.text AS node_text
        FROM meta AS m, stats AS s, thread AS t
        ORDER BY t.path
    """
    
    # Execute SQL query
    result_df = session.sql(
        sql,
        items=items, 
        comments=comments, 
        users=users, 
        root=root
    )
    
    tool_params = [
        ToolParam(
            name="story_id",
            description=(
                "The Hacker News story ID (integer). You can get this from search_stories "
                "results or from HN URLs (e.g., the ID in "
                "https://news.ycombinator.com/item?id=12345 is 12345)."
            ),
        ),
    ]
    
    catalog.create_tool(
        tool_name=tool_name,
        tool_description=(
            "Fetches a complete Hacker News story with its entire comment thread. "
            "Returns one row per comment/story node, maintaining hierarchical structure "
            "via depth and path columns. The path column uses zero-padded IDs "
            "(e.g., '0000012345.0000012346') to show comment hierarchy and maintain sort order. "
            "Includes rich metadata: author karma, domain extraction, comment counts, "
            "and thread depth. Useful for deep discussion analysis."
        ),
        tool_query=result_df,
        tool_params=tool_params,
        result_limit=result_limit,
        ignore_if_exists=False,
    )
    
    print(f"✓ Registered tool: {tool_name}")


# StructTypes for Fenic (matching the Pydantic models)
THEME_STRUCT = StructType([
    StructField("topic", StringType),
    StructField("summary", StringType),
    StructField("stance_spectrum", StringType),
    StructField("representative_comment_ids", ArrayType(IntegerType)),
    StructField("off_topic", BooleanType),
])

SUMMARY_STRUCT = StructType([
    StructField("tl_dr", StringType),
    StructField("story_overview", StringType),
    StructField("key_points", ArrayType(StringType)),
    StructField("discussion_themes", ArrayType(THEME_STRUCT)),
    StructField("variety_present", BooleanType),
    StructField("off_topic_themes", ArrayType(StringType)),
    StructField("risks_or_concerns", ArrayType(StringType)),
    StructField("actionables", ArrayType(StringType)),
    StructField("sources", ArrayType(IntegerType)),
    StructField("truncated_input", BooleanType),
])

# Concise prompt for summarization
CONCISE_PROMPT = """Summarize this Hacker News discussion in {{ language }}:

Story: {{ title }} ({{ domain }})
URL: {{ url }}
Score: {{ score }}, Comments: {{ descendants }}
Published: {{ published_at }}

Discussion thread:
{{ transcript }}

Create a structured summary including:
1. TL;DR (max 2 sentences)
2. Story overview (brief)
3. Key points from discussion
4. Main discussion themes with viewpoints and stances
5. Off-topic themes if present
6. Risks/concerns raised
7. Action items mentioned

{{ extra_instructions }}"""


def register_summarize_story_tool(
    session: Session,
    tool_name: str = "summarize_story",
    result_limit: int = 1,
    model_alias: Optional[str] = None,
) -> None:
    """Register a tool that generates AI-powered structured summaries of HN stories.
    
    Creates comprehensive summaries with discussion themes, viewpoints, concerns,
    and actionables. Automatically detects off-topic branches. Skips LLM call
    if no comments exist.
    
    Examples:
        Basic summary in English:
            story_id: 12345
            
        Summary in Spanish with focus:
            story_id: 12345
            language: "es"
            extra_instructions: "Focus on technical implications"
            
        Limited transcript for faster processing:
            story_id: 12345
            max_transcript_chars: 8000
    """
    
    catalog = session.catalog
    
    # Drop existing tool if it exists
    try:
        catalog.drop_tool(tool_name)
    except:
        pass  # Tool doesn't exist, continue
    
    # Data sources
    items = session.table("items").filter(fc.col("type") == fc.lit("story"))
    comments = session.table("comments")
    
    # Tool parameters
    story_id = fc.tool_param("story_id", IntegerType)
    extra_instructions = fc.tool_param("extra_instructions", StringType)
    language_param = fc.tool_param("language", StringType)
    # Note: max_transcript_chars removed as it can't be used in SQL directly
    
    # Root story selection
    root = items.filter(fc.col("id") == story_id)
    
    # SQL for building transcript
    sql = """
        WITH RECURSIVE thread AS (
            -- Get story
            SELECT
                i.id, i.parent, 0 AS depth,
                lpad(CAST(i.id AS VARCHAR), 10, '0') AS path,
                i.text, i.by, i.score, i.type
            FROM {items} AS i
            WHERE i.id IN (SELECT id FROM {root})
            
            UNION ALL
            
            -- Get comments
            SELECT
                c.id, c.parent, t.depth + 1,
                t.path || '.' || lpad(CAST(c.id AS VARCHAR), 10, '0'),
                c.text, c.by, c.score, c.type
            FROM {comments} AS c
            JOIN thread AS t ON c.parent = t.id
        ),
        formatted AS (
            SELECT
                CASE
                    WHEN depth = 0 THEN '[STORY] ' || COALESCE(text, '')
                    ELSE repeat('  ', depth) || '- [' || COALESCE(by, 'deleted') || ']: ' || COALESCE(text, '')
                END AS line,
                path,
                type = 'comment' AS is_comment
            FROM thread
            WHERE text IS NOT NULL AND text != ''
            ORDER BY path
        ),
        transcript AS (
            SELECT
                string_agg(line, '\n') AS full_transcript,
                CAST(SUM(CASE WHEN is_comment THEN 1 ELSE 0 END) AS BIGINT) AS comments_count,
                MAX(is_comment) AS has_comments
            FROM formatted
        ),
        meta AS (
            SELECT
                CAST(i.id AS BIGINT) AS story_id,
                i.title,
                i.url,
                regexp_extract(i.url, '^(?:https?://)?(?:www\\.)?([^/]+)', 1) AS domain,
                CAST(i.score AS BIGINT) AS score,
                CAST(i.descendants AS BIGINT) AS descendants,
                TIMESTAMP '1970-01-01' + CAST(i.time AS BIGINT) * INTERVAL 1 SECOND AS published_at
            FROM {root} AS i
        ),
        combined AS (
            SELECT 
                m.*,
                t.full_transcript,
                t.comments_count,
                t.has_comments,
                -- Use fixed max chars value
                12000 AS char_limit
            FROM meta m
            CROSS JOIN transcript t
        ),
        final AS (
            SELECT
                *,
                LENGTH(full_transcript) > char_limit AS truncated_input,
                CASE 
                    WHEN LENGTH(full_transcript) > char_limit 
                    THEN SUBSTR(full_transcript, 1, char_limit)
                    ELSE full_transcript
                END AS transcript_limited
            FROM combined
        )
        SELECT * FROM final
    """
    
    # Execute SQL query
    base = session.sql(
        sql,
        items=items,
        comments=comments,
        root=root
    )
    
    # Add default values for optional parameters
    with_params = (
        base
        .with_column("extra", fc.coalesce(extra_instructions, fc.lit("")))
        .with_column("lang", fc.coalesce(language_param, fc.lit("en")))
    )
    
    # Branch 1: Has comments -> summarize
    with_discussion = with_params.filter(fc.col("has_comments") == fc.lit(True))
    
    summary_col = semantic.map(
        CONCISE_PROMPT,
        response_format=StorySummary,
        model_alias=model_alias,
        temperature=0.0,
        max_output_tokens=768,
        title=fc.col("title"),
        url=fc.col("url"),
        domain=fc.col("domain"),
        published_at=fc.col("published_at"),
        score=fc.col("score"),
        descendants=fc.col("descendants"),
        transcript=fc.col("transcript_limited"),
        extra_instructions=fc.col("extra"),
        language=fc.col("lang"),
    )
    
    with_summary = with_discussion.select(
        fc.col("story_id"),
        fc.col("title"),
        fc.col("url"),
        fc.col("domain"),
        fc.col("published_at"),
        fc.col("score"),
        fc.col("descendants"),
        fc.col("comments_count"),
        fc.col("truncated_input"),
        fc.lit("ok").alias("status"),
        fc.lit("").alias("message"),
        summary_col.alias("summary"),
    )
    
    # Branch 2: No comments -> return placeholder
    no_discussion = (
        with_params
        .filter(fc.col("has_comments") == fc.lit(False))
        .select(
            fc.col("story_id"),
            fc.col("title"),
            fc.col("url"),
            fc.col("domain"),
            fc.col("published_at"),
            fc.col("score"),
            fc.col("descendants"),
            fc.col("comments_count"),
            fc.lit(False).alias("truncated_input"),
            fc.lit("no_discussion").alias("status"),
            fc.lit("Story has no comments - summary skipped").alias("message"),
            fc.null(SUMMARY_STRUCT).alias("summary"),
        )
    )
    
    # Union both branches
    result_df = with_summary.union(no_discussion)
    
    # Tool parameters with enhanced descriptions
    tool_params = [
        ToolParam(
            name="story_id",
            description=(
                "The Hacker News story ID to summarize. Get this from search_stories "
                "or read_story results."
            ),
        ),
        ToolParam(
            name="extra_instructions",
            description=(
                "Optional guidance for the summary. Examples: "
                "'Focus on technical details', 'Highlight security concerns', "
                "'Emphasize business implications', 'Extract criticism'"
            ),
            has_default=True,
            default_value="",
        ),
        ToolParam(
            name="language",
            description=(
                "Output language code. Examples: 'en' (English), 'es' (Spanish), "
                "'fr' (French), 'de' (German), 'ja' (Japanese), 'zh' (Chinese)"
            ),
            has_default=True,
            default_value="en",
        ),
    ]
    
    # Create tool with enhanced description
    catalog.create_tool(
        tool_name=tool_name,
        tool_description=(
            "Generate AI-powered structured summary of a Hacker News story and its discussion. "
            "Extracts key themes, viewpoints, concerns, and actionables from the conversation. "
            "Automatically detects off-topic branches and stance variations. "
            "Skips LLM call if no comments exist (returns status='no_discussion'). "
            "Output includes: TL;DR, story overview, discussion themes with stance spectrum, "
            "risks/concerns, and action items. Supports multiple languages and custom focus areas."
        ),
        tool_query=result_df,
        tool_params=tool_params,
        result_limit=result_limit,
        ignore_if_exists=False,
    )
    
    print(f"✓ Registered tool: {tool_name}")


def register_tools(session: Optional[Session] = None, verbose: bool = True) -> None:
    """
    Register all MCP tools for Hacker News data.
    
    Args:
        session: Optional Fenic session to use (creates new if not provided)
        verbose: Whether to print registration progress
    """
    if session is None:
        session = get_session()
    
    if verbose:
        print("Registering MCP tools...")
    
    # Register each tool
    register_story_search_tool(session)
    register_read_story_tool(session)
    register_summarize_story_tool(session)
    
    if verbose:
        print("\nAll tools registered successfully!")


def verify_tools() -> list:
    """
    Verify which tools are registered in the catalog.
    
    Returns:
        List of registered tool names
    """
    session = get_session()
    # Note: This assumes there's a way to list tools from the catalog
    # You may need to adjust based on actual Fenic API
    return []  # Placeholder


if __name__ == "__main__":
    # Register tools when module is run directly
    register_tools()
    
    # Verify registration
    tools = verify_tools()
    if tools:
        print("\nRegistered tools:")
        for tool in tools:
            print(f"  - {tool}")