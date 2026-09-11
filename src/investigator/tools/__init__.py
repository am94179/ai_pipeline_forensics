"""Deterministic evidence-gathering tools for synthetic scenarios."""

from .logs import search_logs
from .pipeline import get_pipeline_status, inspect_pipeline_metadata
from .profiling import compare_distributions, profile_dataset
from .schema import inspect_schema
from .sql import query_data

__all__ = [
    "compare_distributions",
    "get_pipeline_status",
    "inspect_pipeline_metadata",
    "inspect_schema",
    "profile_dataset",
    "query_data",
    "search_logs",
]

