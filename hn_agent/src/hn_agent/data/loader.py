"""
HuggingFace dataset loader for Hacker News data.
"""

from typing import Optional
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from hn_agent.session import get_session


def load_hn_data(verbose: bool = True) -> None:
    """
    Load all Hacker News data from HuggingFace into local tables.
    
    Args:
        verbose: Whether to print loading progress
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


def verify_tables() -> dict:
    """
    Verify that all tables were loaded and return their record counts.
    
    Returns:
        Dictionary mapping table names to record counts
    """
    session = get_session()
    expected_tables = [
        "comments", "items", "stories", "jobs", "polls",
        "pollopts", "users", "user_submissions", 
        "item_children", "item_parts"
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