"""
Step 3: SQL generation

Given a question and the relevant tables (from Step 2), this
generates the actual SQL query using the hosted LLM.
"""

from identify_tables import call_llm

# ---------------------------------------------------------------
# SAMPLE schema - replace with the real schema once Step 1 is ready.
# Keep the same shape (table name -> full column list) and nothing
# else needs to change.
# ---------------------------------------------------------------
FULL_SCHEMA = {
    "customers": "customers(id, name, email, signup_date)",
    "orders": "orders(id, customer_id, product_id, sale_date)",
    "products": "products(id, name, color, category, price)",
    "inventory": "inventory(id, product_id, warehouse_id, stock_count)",
    "reviews": "reviews(id, customer_id, product_id, rating, comment)",
}


def generate_sql(question: str, relevant_tables: list[str]) -> str:
    schema_text = "\n".join(FULL_SCHEMA[t] for t in relevant_tables)

    prompt = f"""You are a SQL expert. Write a single SQL query to answer the question below,
using ONLY the tables provided. Reply with ONLY the SQL query, no explanation.

Question: "{question}"

Tables:
{schema_text}
"""

    sql = call_llm(prompt)
    sql = sql.strip()
    sql = sql.removeprefix("```sql").removeprefix("```").removesuffix("```").strip()
    return sql


# ---------------------------------------------------------------
# Quick test - run this file directly to test Step 3 alone
# (uses a hardcoded table list instead of calling Step 2)
# ---------------------------------------------------------------
if __name__ == "__main__":
    test_question = "How many red products were sold in June?"
    test_tables = ["orders", "products"]

    print("Question:", test_question)
    print("Using tables:", test_tables)

    sql = generate_sql(test_question, test_tables)
    print("Generated SQL:\n", sql)