"""
FastAPI server for the Chinook Text-to-SQL project
---------------------------------------------------
This is the missing piece between the frontend (frontend/index.html)
and the pipeline that already works from the command line (main.py).

It exposes exactly the two endpoints the frontend already calls:

    GET  /health   -> lets the frontend show "Database connected" / "offline"
    POST /query    -> { "question": "..." } goes in,
                       { success, question, tables, sql, rows, chart, error } comes out

Under the hood it reuses the exact same functions main.py uses:
    relevant_tables()  -> Step 2 (llm_logic/llm_sql_logic.py)
    generate_sql()      -> Step 3 (llm_logic/llm_sql_logic.py)
    run_sql()           -> Step 4 (toolbox_setup/run_query.py)
    suggest_chart()     -> decides if/how to chart the result (chart_logic/chart_logic.py)

How to run it:
    1. Make sure the Toolbox server is running in its own terminal:
           toolbox --tools-file="toolbox_setup/tools.yaml" --port 5000
    2. In another terminal, from this folder, run:
           uvicorn server:app --reload --port 8000
    3. Open frontend/index.html in your browser (just double-click it,
       or use a "Live Server" extension). It already points at
       http://localhost:8000, so it will find this server automatically.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from llm_logic.llm_sql_logic import relevant_tables, generate_sql
from toolbox_setup.run_query import get_schema, run_sql
from chart_logic.chart_logic import suggest_chart

app = FastAPI(title="Chinook Text-to-SQL API")

# The frontend HTML file is opened directly in the browser (or via a
# separate dev server), which is a different "origin" than this API.
# Without CORS enabled, the browser blocks the fetch() calls entirely.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class QuestionRequest(BaseModel):
    question: str


@app.get("/health")
async def health():
    """
    The frontend calls this once on page load to show the green
    "Database connected" badge (or red "API server offline" if this
    fails). We confirm the whole chain works by loading the schema
    through Toolbox, just like main.py does at startup.
    """
    try:
        await get_schema()
        return {"status": "ok"}
    except Exception as error:
        # Returning a non-2xx status is what makes the frontend show
        # the red "offline" badge instead of the green one.
        raise HTTPException(status_code=503, detail=str(error))


@app.post("/query")
async def query(payload: QuestionRequest):
    """
    Runs one question through the full pipeline:
        question -> relevant_tables() -> generate_sql() -> run_sql() -> suggest_chart()

    Always returns 200 OK with a JSON body the frontend already knows
    how to render - success/failure is communicated via the "success"
    field, not via HTTP status codes, so the UI can show a nice error
    card instead of a generic browser error.
    """
    question = payload.question.strip()

    if not question:
        return {
            "success": False,
            "question": question,
            "tables": [],
            "sql": "",
            "error": "Question cannot be empty.",
        }

    # Step 2: which tables are relevant?
    try:
        tables = relevant_tables(question)
    except Exception as error:
        return {
            "success": False,
            "question": question,
            "tables": [],
            "sql": "",
            "error": f"Could not determine relevant tables: {error}",
        }

    if not tables:
        return {
            "success": False,
            "question": question,
            "tables": [],
            "sql": "",
            "error": "Could not determine relevant tables for that question. Try rephrasing.",
        }

    # Step 3: ask the LLM to write the SQL
    try:
        sql = generate_sql(question, tables)
    except Exception as error:
        return {
            "success": False,
            "question": question,
            "tables": tables,
            "sql": "",
            "error": f"Could not generate SQL: {error}",
        }

    # Step 4: run it against the real database through MCP Toolbox
    result = await run_sql(sql)

    if result["success"]:
        # Step 5: decide if/how this result can be shown as a chart
        chart_info = suggest_chart(result["rows"])

        return {
            "success": True,
            "question": question,
            "tables": tables,
            "sql": sql,
            "rows": result["rows"],
            "chart": chart_info,
        }

    return {
        "success": False,
        "question": question,
        "tables": tables,
        "sql": sql,
        "error": result["error"],
    }