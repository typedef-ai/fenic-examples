"""
HuggingFace dataset loader for Hacker News data.
"""

from typing import Optional
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from hn_agent.session import get_session
from hn_agent.data.denormalize import denormalize_all
from hn_agent.data.format_threads import format_all_threads


def load_hn_data(verbose: bool = True, denormalize: bool = True, format_threads: bool = True) -> None:
    """
    Load all Hacker News data from HuggingFace into local tables.

    Pipeline:
    1. Load base tables from HuggingFace
    2. Denormalize recursive relationships (comment_to_story, story_threads)
    3. Format threads into markdown discussions (story_discussions)

    Args:
        verbose: Whether to print loading progress
        denormalize: Whether to denormalize relationships after loading (default: True)
        format_threads: Whether to format discussions after denormalization (default: True)
    """
    session = get_session()
    base_path = "hf://datasets/typedef-ai/hacker-news-dataset/data"

    # All 2025 data files to load
    files_to_tables = {
        "2025_comments": "comments",
        "2025_items": "items",
        "2025_stories": "stories",
        "2025_jobs": "jobs",
        "2025_polls": "polls",
        "2025_pollopts": "pollopts",
        "2025_users": "users",
        "2025_user_submissions": "user_submissions",
        "2025_item_children": "item_children",
        "2025_item_parts": "item_parts"
    }

    # Load each file into its own table
    for file_name, table_name in files_to_tables.items():
        if verbose:
            print(f"Loading {file_name}...")

        df = session.read.parquet(f"{base_path}/{file_name}.parquet")
        df.write.save_as_table(table_name, mode="overwrite")

        if verbose:
            count = df.count()
            print(f"  ✓ Loaded {count:,} records into {table_name}")

    # Step 2: Denormalize relationships
    if denormalize:
        denormalize_all(session=session, verbose=verbose)

    # Step 3: Format threads
    if format_threads:
        format_all_threads(session=session, verbose=verbose)


def verify_tables() -> dict:
    """
    Verify that all tables were loaded and return their record counts.

    Returns:
        Dictionary mapping table names to record counts
    """
    session = get_session()
    expected_tables = [
        # Base tables from HuggingFace
        "comments", "items", "stories", "jobs", "polls",
        "pollopts", "users", "user_submissions",
        "item_children", "item_parts",
        # Denormalized tables
        "comment_to_story", "story_threads",
        # Formatted tables
        "story_discussions"
    ]

    table_counts = {}
    for table_name in expected_tables:
        if session.catalog.does_table_exist(table_name):
            df = session.table(table_name)
            table_counts[table_name] = df.count()
        else:
            table_counts[table_name] = None

    return table_counts


if __name__ == "__main__":
    # Load data when module is run directly
    load_hn_data()
    
    # Verify tables
    counts = verify_tables()
    print("\nTable verification:")
    for table, count in counts.items():
        if count is not None:
            print(f"  {table}: {count:,} records")
        else:
            print(f"  {table}: NOT LOADED")