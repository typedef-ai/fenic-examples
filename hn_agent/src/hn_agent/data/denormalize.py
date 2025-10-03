"""
Denormalize recursive parent-child relationships into flat lookup tables.

This module creates optimized lookup tables that eliminate the need for
recursive SQL queries during MCP tool execution:

1. comment_to_story - Denormalized comment→story mappings
2. story_threads - Denormalized thread structure with depth and hierarchical path
"""

import sys
from pathlib import Path
from typing import Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import fenic as fc


def precalculate_comment_to_story(session: fc.Session, verbose: bool = True) -> None:
    """
    Create comment_to_story lookup table.

    Maps every comment to its root story by recursively traversing the parent
    chain. This replaces recursive SQL #1 in tools.py.

    Schema:
        comment_id: int64 - The comment ID
        story_id: int64 - The root story ID this comment belongs to
        depth: int32 - How many levels up to reach the story (0 = direct reply)

    Args:
        session: Fenic session
        verbose: Whether to print progress
    """
    if verbose:
        print("Creating comment_to_story lookup table...")

    # Source tables
    items = session.table("items")
    comments = session.table("comments")

    # Recursive SQL to trace comments to their root stories
    sql = """
        WITH RECURSIVE up(comment_id, parent_id, story_id, depth) AS (
            -- Base case: comments with their immediate parent
            SELECT
                c.id as comment_id,
                c.parent as parent_id,
                CASE WHEN p.type = 'story' THEN p.id ELSE NULL END as story_id,
                0 as depth
            FROM {comments} c
            LEFT JOIN {items} p ON c.parent = p.id

            UNION ALL

            -- Recursive case: traverse up the parent chain
            SELECT
                up.comment_id,
                p.parent as parent_id,
                CASE
                    WHEN p.type = 'story' THEN p.id
                    ELSE up.story_id
                END as story_id,
                up.depth + 1
            FROM up
            JOIN {items} p ON up.parent_id = p.id
            WHERE up.story_id IS NULL
              AND up.depth < 20  -- Safety limit
        )
        SELECT DISTINCT
            comment_id,
            story_id,
            depth
        FROM up
        WHERE story_id IS NOT NULL
    """

    # Execute and save
    df = session.sql(sql, comments=comments, items=items)
    df.write.save_as_table("comment_to_story", mode="overwrite")

    if verbose:
        count = df.count()
        print(f"  ✓ Created comment_to_story: {count:,} comment→story mappings")


def precalculate_story_threads(session: fc.Session, verbose: bool = True) -> None:
    """
    Create story_threads materialized table.

    Precomputes the full thread structure for all stories with their comments,
    including depth and hierarchical path. This replaces recursive SQL #2 and #3
    in tools.py.

    Schema:
        story_id: int64 - The root story ID
        node_id: int64 - ID of this node (story or comment)
        parent_id: int64 - Parent node ID (NULL for story)
        depth: int32 - Nesting level (0 = story, 1 = direct reply, etc)
        path: string - Hierarchical path for sorting (e.g., "0000012345.0000012346")
        type: string - Node type ("story" or "comment")
        by: string - Author username
        text: string - Content text
        time: int64 - Unix timestamp
        score: int32 - Score/points

    Args:
        session: Fenic session
        verbose: Whether to print progress
    """
    if verbose:
        print("Creating story_threads materialized table...")

    # Source tables
    items = session.table("items")
    comments = session.table("comments")

    # Recursive SQL to build full threads
    sql = """
        WITH RECURSIVE thread AS (
            -- Base case: all stories
            SELECT
                i.id as story_id,
                i.id as node_id,
                i.parent as parent_id,
                0 AS depth,
                lpad(CAST(i.id AS VARCHAR), 10, '0') AS path,
                i.type,
                i.by,
                i.text,
                i.time,
                i.score
            FROM {items} AS i
            WHERE i.type = 'story'

            UNION ALL

            -- Recursive case: all comments
            SELECT
                t.story_id,
                c.id as node_id,
                c.parent as parent_id,
                t.depth + 1,
                t.path || '.' || lpad(CAST(c.id AS VARCHAR), 10, '0') AS path,
                c.type,
                c.by,
                c.text,
                c.time,
                c.score
            FROM {comments} AS c
            JOIN thread AS t ON c.parent = t.node_id
            WHERE t.depth < 20  -- Safety limit
        )
        SELECT * FROM thread
        ORDER BY path
    """

    # Execute and save
    df = session.sql(sql, items=items, comments=comments)
    df.write.save_as_table("story_threads", mode="overwrite")

    if verbose:
        count = df.count()
        print(f"  ✓ Created story_threads: {count:,} nodes (stories + comments)")


def denormalize_all(session: Optional[fc.Session] = None, verbose: bool = True) -> None:
    """
    Run all denormalization steps.

    Args:
        session: Optional Fenic session (creates new if not provided)
        verbose: Whether to print progress
    """
    if session is None:
        from hn_agent.session import get_session
        session = get_session()

    if verbose:
        print("\nDenormalizing recursive relationships...")

    # Create both lookup tables
    precalculate_comment_to_story(session, verbose=verbose)
    precalculate_story_threads(session, verbose=verbose)

    if verbose:
        print("\n✓ All denormalized tables created successfully!")


if __name__ == "__main__":
    # Run denormalization when module is executed directly
    denormalize_all()
