"""
Text-to-SQL over the Chinook database (MCP Toolbox + hosted LLM)
------------------------------------------------------------------
This file is the glue between everyone's parts:

    Step 1 (teammate, toolbox_setup/run_query.py)  -> get_schema()
    Step 2 (you,      llm_logic/llm_sql_logic.py)   -> relevant_tables()
    Step 3 (you,      llm_logic/llm_sql_logic.py)   -> generate_sql()
    Step 4 (teammate, toolbox_setup/run_query.py)   -> run_sql()

Flow for each question typed by the user:
    question
        -> relevant_tables(question)       # Step 2: which 2-3 tables?
        -> generate_sql(question, tables)  # Step 3: LLM writes SQL
        -> run_sql(sql)                    # Step 4: execute via Toolbox
        -> print rows or a readable error

Prerequisite: the Toolbox server must already be running in a separate
terminal (see README.md), using this project's tools.yaml:

    toolbox --tools-file="toolbox_setup/tools.yaml" --port 5000
"""

import asyncio

from llm_logic.llm_sql_logic import relevant_tables, generate_sql
from toolbox_setup.run_query import get_schema, run_sql


async def answer_question(question: str) -> None:
    """Runs one question through the full Step 2 -> 3 -> 4 pipeline."""

    # Step 2: figure out which tables matter
    tables = relevant_tables(question)
    if not tables:
        print("Could not determine relevant tables for that question. Try rephrasing.")
        return
    print(f"Relevant tables: {tables}")

    # Step 3: ask the LLM to write the SQL
    sql = generate_sql(question, tables)
    print(f"\nGenerated SQL:\n{sql}\n")

    # Step 4: run it against the real database through MCP Toolbox
    result = await run_sql(sql)

    if result["success"]:
        rows = result["rows"]
        if not rows:
            print("Query ran successfully but returned no rows.")
        else:
            print("Results:")
            for row in rows:
                print(row)
    else:
        print("Query failed:")
        print(result["error"])


async def main() -> None:
    # Optional: confirm the Toolbox connection + schema load works
    # before taking any questions (comment out if it's too noisy).
    try:
        await get_schema()
        print("Connected to Toolbox and loaded schema successfully.\n")
    except Exception as error:
        print(f"Could not connect to Toolbox server: {error}")
        print("Make sure toolbox.exe is running (see README.md) before continuing.\n")
        return

    print("Ask a question about the Chinook database (or type 'exit' to quit).\n")

    while True:
        question = input("Question: ").strip()
        if not question:
            continue
        if question.lower() in {"exit", "quit"}:
            break

        print()
        try:
            await answer_question(question)
        except Exception as error:
            print(f"Something went wrong processing that question: {error}")
        print("\n" + "-" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())