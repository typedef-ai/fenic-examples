"""
Format denormalized thread data into human-readable markdown discussions.

This module creates a materialized table with story metadata and formatted
discussion threads, making it easy to present complete HN conversations.
"""

import sys
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
import html

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import fenic as fc
from fenic.api.functions.builtin import udf
from fenic.core.types.datatypes import StringType, StructType, ArrayType, IntegerType, StructField


def format_thread_to_markdown(comments: List[Dict[str, Any]]) -> str:
    """
    Format a list of comment structs into nested markdown list.

    Args:
        comments: List of dicts with keys: depth, by, score, time, text

    Returns:
        Markdown formatted string with nested comments
    """
    if not comments:
        return ""

    lines = []

    for comment in comments:
        depth = comment.get('depth', 0)
        author = comment.get('by', '[deleted]')
        score = comment.get('score', 0)
        timestamp = comment.get('time', 0)
        text = comment.get('text', '')

        # Skip if no author or text (deleted comments)
        if not author or not text:
            continue

        # Convert Unix timestamp to ISO format
        try:
            dt = datetime.fromtimestamp(timestamp, tz=datetime.UTC)
            time_str = dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        except:
            time_str = 'unknown'

        # Decode HTML entities
        text_decoded = html.unescape(text)

        # Calculate indentation (2 spaces per depth level, minus 1 since depth starts at 1 for comments)
        indent = '  ' * (depth - 1) if depth > 0 else ''

        # Format as markdown list item
        line = f"{indent}- [{author}] (score: {score}, {time_str}): {text_decoded}"
        lines.append(line)

    return '\n'.join(lines)


# Register the UDF
@udf(return_type=StringType)
def format_thread_udf(comments: List[Dict[str, Any]]) -> str:
    """UDF wrapper for format_thread_to_markdown."""
    return format_thread_to_markdown(comments)


def format_all_threads(session: Optional[fc.Session] = None, verbose: bool = True) -> None:
    """
    Create story_discussions table with metadata and formatted markdown threads.

    Args:
        session: Optional Fenic session (creates new if not provided)
        verbose: Whether to print progress
    """
    if session is None:
        from hn_agent.session import get_session
        session = get_session()

    if verbose:
        print("Formatting thread discussions...")

    # Source tables
    items = session.table("items")
    story_threads = session.table("story_threads")

    # Step 1: Aggregate story metadata
    story_metadata_sql = """
        SELECT
            i.id as story_id,
            i.title,
            i.url,
            regexp_extract(i.url, '^(?:https?://)?(?:www\\.)?([^/]+)', 1) AS domain,
            i.by as story_author,
            i.score as story_score,
            i.text as story_text,
            TIMESTAMP '1970-01-01' + CAST(i.time AS BIGINT) * INTERVAL 1 SECOND AS published_at,
            i.descendants as comment_count
        FROM {items} i
        WHERE i.type = 'story'
    """

    story_meta_df = session.sql(story_metadata_sql, items=items)

    # Step 2: Aggregate comments by story with stats
    comments_agg_sql = """
        SELECT
            story_id,
            COUNT(*) as total_nodes,
            COUNT(DISTINCT by) as unique_commenters,
            MAX(depth) as max_depth,
            LIST(
                {'depth': depth, 'by': by, 'score': score, 'time': time, 'text': text}
                ORDER BY path
            ) as comment_list
        FROM {story_threads}
        WHERE depth > 0  -- Only comments, not the story itself
        GROUP BY story_id
    """

    comments_agg_df = session.sql(comments_agg_sql, story_threads=story_threads)

    # Step 3: Join metadata with aggregated comments
    combined_df = (
        story_meta_df
        .join(comments_agg_df, on="story_id", how="left")
    )

    # Step 4: Apply UDF to format threads
    formatted_df = combined_df.with_column(
        "markdown_thread",
        fc.when(
            fc.col("comment_list").is_not_null(),
            format_thread_udf(fc.col("comment_list"))
        ).otherwise(fc.lit(""))
    )

    # Step 5: Select final columns (use SQL for current_timestamp)
    final_sql = """
        SELECT
            story_id,
            title,
            url,
            domain,
            story_author,
            story_score,
            story_text,
            published_at,
            comment_count,
            COALESCE(unique_commenters, 0) as unique_commenters,
            COALESCE(max_depth, 0) as max_depth,
            markdown_thread,
            CURRENT_TIMESTAMP as generated_at
        FROM {formatted}
    """

    final_df = session.sql(final_sql, formatted=formatted_df)

    # Save as table
    final_df.write.save_as_table("story_discussions", mode="overwrite")

    if verbose:
        count = final_df.count()
        print(f"  ✓ Created story_discussions: {count:,} formatted threads")


if __name__ == "__main__":
    # Run formatting when module is executed directly
    format_all_threads()
