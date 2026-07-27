"""
MCP Toolbox connection: Step 1 + Step 4
-----------------------------------------
Step 1: Connect to the Chinook database (SQL Server) via MCP Toolbox,
        and load the schema using the list_tables tool.
Step 4: Take a SQL string (produced by your teammate's generate_sql())
        and run it via execute_sql, handling results and errors.

Prerequisite: the Toolbox server must already be running in a separate
terminal, using this project's tools.yaml:

    toolbox --tools-file="tools.yaml" --port 5000

Leave that terminal open while you run this script.
"""

import asyncio
from toolbox_core import ToolboxClient

TOOLBOX_URL = "http://127.0.0.1:5000"
TOOLSET_NAME = "chinook_tools"


# ---------------------------------------------------------------------------
# Step 1: connect + load schema
# ---------------------------------------------------------------------------

async def get_schema():
    """
    Connects to the Toolbox server and calls list_tables to pull back
    live schema info (columns, types, relationships) straight from
    the real Chinook database in SSMS - no manual typing needed.
    """
    async with ToolboxClient(TOOLBOX_URL) as toolbox:
        list_tables_tool = await toolbox.load_tool("list_tables")
        schema = await list_tables_tool()
        return schema


# ---------------------------------------------------------------------------
# Step 4: run generated SQL + handle results/errors
# ---------------------------------------------------------------------------

async def run_sql(sql_query):
    """
    Takes a SQL string (from your teammate's generate_sql()) and executes
    it against the real database through MCP Toolbox.

    Returns a dict shaped like:
        {"success": True,  "rows": [...]}
        {"success": False, "error": "readable error message"}

    This shape is the "contract" the rest of the app can rely on -
    whoever calls run_sql() never needs to catch exceptions themselves.
    """
    try:
        async with ToolboxClient(TOOLBOX_URL) as toolbox:
            execute_sql_tool = await toolbox.load_tool("execute_sql")
            result = await execute_sql_tool(sql=sql_query)
            return {"success": True, "rows": result}

    except Exception as error:
        # Common causes here: bad table/column name in the generated SQL,
        # SQL Server syntax the LLM got wrong (e.g. LIMIT instead of TOP),
        # or the Toolbox server / SQL Server not being reachable at all.
        return {
            "success": False,
            "error": f"Query failed: {error}",
            "attempted_sql": sql_query,
        }


# ---------------------------------------------------------------------------
# Quick manual test - run this file directly
# ---------------------------------------------------------------------------

async def _demo():
    print("Step 1 - loading schema via list_tables...\n")
    schema = await get_schema()
    print(schema)

    print("\nStep 4 - running a test query via execute_sql...\n")
    test_sql = "SELECT TOP 5 Name FROM Artist ORDER BY Name;"
    result = await run_sql(test_sql)

    if result["success"]:
        print("Query succeeded. Rows returned:")
        print(result["rows"])
    else:
        print("Query failed:")
        print(result["error"])


if __name__ == "__main__":
    asyncio.run(_demo())