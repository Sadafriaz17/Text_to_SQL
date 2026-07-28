"""
FastAPI backend for the Text-to-SQL Chinook application.
---------------------------------------------------------
Exposes two endpoints:
    GET  /health  – checks that the Toolbox server is reachable
    POST /query   – runs the full pipeline for a natural-language question

Start with:
    uvicorn api:app --port 8000 --reload

Prerequisite: Toolbox server must already be running on port 5000.
"""

import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Optional

from llm_logic.llm_sql_logic import relevant_tables, generate_sql
from toolbox_setup.run_query import get_schema, run_sql

app = FastAPI(
    title="Text-to-SQL Chinook API",
    description="Natural language queries over the Chinook music database.",
    version="1.0.0",
)

# Allow the frontend (any origin during development) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    success: bool
    question: str
    tables: list[str]
    sql: str
    rows: Optional[list[Any]] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", summary="Check Toolbox connectivity")
async def health():
    """Attempts to load the schema via MCP Toolbox; returns 200 on success."""
    try:
        await get_schema()
        return {"status": "ok", "toolbox": "connected"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Toolbox not reachable: {exc}")


@app.post("/query", response_model=QueryResponse, summary="Run a natural-language query")
async def query(req: QueryRequest):
    """
    Runs the full pipeline:
      Step 2 – relevant_tables()  (LLM picks 2-3 tables)
      Step 3 – generate_sql()     (LLM writes T-SQL)
      Step 4 – run_sql()          (Toolbox executes against SQL Server)
    """
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Question must not be empty.")

    # Step 2 ─ which tables?
    try:
        tables = relevant_tables(question)
    except Exception as exc:
        return QueryResponse(
            success=False,
            question=question,
            tables=[],
            sql="",
            error=f"Table-selection failed: {exc}",
        )

    if not tables:
        return QueryResponse(
            success=False,
            question=question,
            tables=[],
            sql="",
            error="Could not determine relevant tables. Try rephrasing your question.",
        )

    # Step 3 ─ generate SQL
    try:
        sql = generate_sql(question, tables)
    except Exception as exc:
        return QueryResponse(
            success=False,
            question=question,
            tables=tables,
            sql="",
            error=f"SQL generation failed: {exc}",
        )

    # Step 4 ─ run it
    result = await run_sql(sql)

    if result["success"]:
        return QueryResponse(
            success=True,
            question=question,
            tables=tables,
            sql=sql,
            rows=result["rows"],
        )
    else:
        return QueryResponse(
            success=False,
            question=question,
            tables=tables,
            sql=sql,
            error=result.get("error", "Unknown error"),
        )
