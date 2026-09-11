"""Read-only DuckDB queries over named public scenario datasets."""

from __future__ import annotations

import re
from pathlib import Path

import duckdb

from .common import DATASET_PATHS, ToolInputError, dataset_path

_READ_ONLY_QUERY = re.compile(r"^(SELECT|WITH)\b", re.IGNORECASE)
_DISALLOWED_KEYWORD = re.compile(r"\b(INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|COPY|ATTACH|DETACH|INSTALL|LOAD|PRAGMA|CALL)\b", re.IGNORECASE)


def query_data(scenario_dir: Path, query: str) -> dict[str, object]:
    """Run a single read-only SQL query over registered scenario dataset views."""
    normalized_query = query.strip().rstrip(";").strip()
    if not normalized_query or not _READ_ONLY_QUERY.match(normalized_query) or ";" in normalized_query or _DISALLOWED_KEYWORD.search(normalized_query):
        raise ToolInputError("Only one SELECT or WITH query is allowed.")

    connection = duckdb.connect(database=":memory:")
    try:
        for view_name in DATASET_PATHS:
            path = dataset_path(scenario_dir, view_name)
            escaped_path = str(path).replace("'", "''")
            connection.execute(
                f"CREATE VIEW {view_name} AS SELECT * FROM read_csv_auto('{escaped_path}')"
            )
        result = connection.execute(normalized_query)
        columns = [description[0] for description in result.description]
        rows = [dict(zip(columns, row, strict=True)) for row in result.fetchall()]
        return {"query": normalized_query, "columns": columns, "row_count": len(rows), "rows": rows}
    except duckdb.Error as error:
        raise ToolInputError(f"SQL query failed: {error}") from error
    finally:
        connection.close()

