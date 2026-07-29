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
import json
import os

from dotenv import load_dotenv
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import service_account
from toolbox_core import ToolboxClient

load_dotenv()

TOOLBOX_URL = "http://127.0.0.1:5000"
TOOLSET_NAME = "chinook_tools"

# ---------------------------------------------------------------------------
# Auth: mint a Google ID token for the Toolbox's "toolbox-auth" authService
# (see tools.yaml). This is a service-account token, not a human login - it
# proves the *backend* is a trusted caller, matching the GOOGLE_CLIENT_ID
# configured as that authService's clientId.
# ---------------------------------------------------------------------------

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
_KEY_FILE_NAME = os.environ.get("GOOGLE_SERVICE_ACCOUNT_KEY_FILE")
GOOGLE_SERVICE_ACCOUNT_KEY_PATH = (
    os.path.join(os.path.dirname(__file__), _KEY_FILE_NAME) if _KEY_FILE_NAME else None
)


async def get_auth_token():
    """
    Returns a fresh Google-signed ID token whose audience matches
    GOOGLE_CLIENT_ID. Called by the Toolbox SDK on every tool invocation -
    minting a new one each time keeps it from ever going stale.
    """
    if not GOOGLE_CLIENT_ID or not GOOGLE_SERVICE_ACCOUNT_KEY_PATH:
        raise ValueError(
            "GOOGLE_CLIENT_ID and GOOGLE_SERVICE_ACCOUNT_KEY_FILE must be set in "
            ".env - see toolbox_setup/tools.yaml's authServices for why this is required."
        )

    credentials = service_account.IDTokenCredentials.from_service_account_file(
        GOOGLE_SERVICE_ACCOUNT_KEY_PATH, target_audience=GOOGLE_CLIENT_ID
    )
    credentials.refresh(GoogleAuthRequest())
    return credentials.token


AUTH_TOKEN_GETTERS = {"toolbox-auth": get_auth_token}


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
        list_tables_tool = await toolbox.load_tool(
            "list_tables", auth_token_getters=AUTH_TOKEN_GETTERS
        )
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
            execute_sql_tool = await toolbox.load_tool(
                "execute_sql", auth_token_getters=AUTH_TOKEN_GETTERS
            )
            result = await execute_sql_tool(sql=sql_query)
            return {"success": True, "rows": _normalize_rows(result)}

    except Exception as error:
        # Common causes here: bad table/column name in the generated SQL,
        # SQL Server syntax the LLM got wrong (e.g. LIMIT instead of TOP),
        # or the Toolbox server / SQL Server not being reachable at all.
        return {
            "success": False,
            "error": f"Query failed: {error}",
            "attempted_sql": sql_query,
        }


def _normalize_rows(result):
    """
    execute_sql_tool() can return rows already as a Python list of dicts,
    OR as a JSON-encoded string, depending on the Toolbox version/tool
    config. The frontend always needs a real list (it calls .map() on
    it), so this makes sure that's what it gets no matter which shape
    Toolbox handed back - avoiding a confusing "rows.map is not a
    function" crash in the browser that looks like a network error but
    isn't.
    """
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except json.JSONDecodeError:
            # Not JSON at all - wrap it so the frontend still gets a list
            return [{"result": result}]
    if isinstance(result, list):
        return result
    # A single row comes back as a lone dict (not a one-item list), same as
    # any other unexpected type - wrap defensively rather than crash later.
    return [result]


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