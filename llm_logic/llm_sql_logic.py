"""
Text-to-SQL: LLM logic (Step 2 + Step 3)
------------------------------------------
This is YOUR part of the project. It has two jobs:

  Step 2 - relevant_tables(): given a question, ask the LLM which 2-3
           Chinook tables are actually needed to answer it.
  Step 3 - generate_sql():    given the question + the FULL schema of
           just those tables, ask the LLM to write one SQL query.

Your teammate's code (Step 1 + Step 4) will:
  - hand you the list of table names + descriptions (Step 1, list_tables)
  - take the SQL string you return and run it via MCP Toolbox's execute_sql (Step 4)

So the "contract" between your code and theirs is simple:
  - You RECEIVE: a question (string) and table info (dict)
  - You RETURN: a list of table names, then a SQL string
No database connection happens in this file at all - that's their job.
"""

import json
import re
import requests

# ---------------------------------------------------------------------------
# 1. Connect to the hosted LLM
# ---------------------------------------------------------------------------

LLM_URL = "http://10.41.4.200:4000/v1/chat/completions"
LLM_API_KEY = "sk-ZV5gXGf-kd8r9wvUcHgNqw"
LLM_MODEL = "qwen/qwen3.6-27b"


def call_llm(messages, temperature=0.0):
    """
    Sends a list of chat messages to the hosted model and returns the
    plain text of its reply.

    messages looks like:
        [{"role": "user", "content": "Hello!"}]

    temperature=0.0 keeps answers consistent/predictable, which matters
    a lot for SQL generation - you don't want a "creative" query.
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LLM_API_KEY}",
    }
    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
    }

    response = requests.post(LLM_URL, headers=headers, json=payload, timeout=60)
    response.raise_for_status()  # throws an error if the server returned a failure
    data = response.json()

    # This is the standard OpenAI-style response shape, which this
    # endpoint follows (it's why the curl command looks like OpenAI's API).
    return data["choices"][0]["message"]["content"]


# ---------------------------------------------------------------------------
# 2. Reference data: short descriptions of every Chinook table
#    (Your teammate may eventually replace this with live list_tables()
#    output from MCP Toolbox - for now, hardcoding it lets you build and
#    test your part independently.)
# ---------------------------------------------------------------------------

TABLE_DESCRIPTIONS = {
    "Artist": "Music artists/bands. Just an ID and a name.",
    "Album": "Albums, each linked to one Artist.",
    "Track": "Individual songs, each linked to one Album, Genre, and MediaType. Has price and duration.",
    "Genre": "Music genres like Rock, Jazz, Metal.",
    "MediaType": "File formats like MPEG audio, AAC audio file.",
    "Playlist": "Named playlists (e.g. 'Music', 'Movies').",
    "PlaylistTrack": "Links Playlists to the Tracks inside them (many-to-many).",
    "Customer": "People who bought music. Name, email, country, and their assigned SupportRep (Employee).",
    "Invoice": "One purchase/order made by a Customer, with a date and total.",
    "InvoiceLine": "Individual line items within an Invoice - which Track, quantity, price.",
    "Employee": "Staff, including sales support reps. Has a ReportsTo manager hierarchy.",
}

# Full column-level schema, but ONLY needed for the 2-3 tables the LLM
# picks in Step 2 - this keeps Step 3's prompt short and focused.
TABLE_SCHEMAS = {
    "Artist": "Artist(ArtistId INT PRIMARY KEY, Name NVARCHAR(120))",
    "Album": "Album(AlbumId INT PRIMARY KEY, Title NVARCHAR(160), ArtistId INT REFERENCES Artist(ArtistId))",
    "Track": (
        "Track(TrackId INT PRIMARY KEY, Name NVARCHAR(200), AlbumId INT REFERENCES Album(AlbumId), "
        "MediaTypeId INT REFERENCES MediaType(MediaTypeId), GenreId INT REFERENCES Genre(GenreId), "
        "Composer NVARCHAR(220), Milliseconds INT, Bytes INT, UnitPrice DECIMAL(10,2))"
    ),
    "Genre": "Genre(GenreId INT PRIMARY KEY, Name NVARCHAR(120))",
    "MediaType": "MediaType(MediaTypeId INT PRIMARY KEY, Name NVARCHAR(120))",
    "Playlist": "Playlist(PlaylistId INT PRIMARY KEY, Name NVARCHAR(120))",
    "PlaylistTrack": "PlaylistTrack(PlaylistId INT REFERENCES Playlist(PlaylistId), TrackId INT REFERENCES Track(TrackId))",
    "Customer": (
        "Customer(CustomerId INT PRIMARY KEY, FirstName NVARCHAR(40), LastName NVARCHAR(20), Country NVARCHAR(40), "
        "Email NVARCHAR(60), SupportRepId INT REFERENCES Employee(EmployeeId))"
    ),
    "Invoice": (
        "Invoice(InvoiceId INT PRIMARY KEY, CustomerId INT REFERENCES Customer(CustomerId), "
        "InvoiceDate DATETIME, BillingCountry NVARCHAR(40), Total DECIMAL(10,2))"
    ),
    "InvoiceLine": (
        "InvoiceLine(InvoiceLineId INT PRIMARY KEY, InvoiceId INT REFERENCES Invoice(InvoiceId), "
        "TrackId INT REFERENCES Track(TrackId), UnitPrice DECIMAL(10,2), Quantity INT)"
    ),
    "Employee": (
        "Employee(EmployeeId INT PRIMARY KEY, FirstName NVARCHAR(20), LastName NVARCHAR(20), Title NVARCHAR(30), "
        "ReportsTo INT REFERENCES Employee(EmployeeId))"
    ),
}


# ---------------------------------------------------------------------------
# 3. STEP 2 - relevant table filter
# ---------------------------------------------------------------------------

def relevant_tables(question, table_descriptions=TABLE_DESCRIPTIONS):
    """
    Asks the LLM: "given this question, which 2-3 tables do you actually need?"
    Returns a Python list of table name strings, e.g. ["Artist", "Album"].
    """
    menu = "\n".join(f"- {name}: {desc}" for name, desc in table_descriptions.items())

    prompt = f"""You are helping choose which database tables are needed to answer a question.

Available tables:
{menu}

Question: "{question}"

Pick the 2 or 3 tables that are actually needed to answer this question.
Respond with ONLY a JSON array of table names, nothing else. No explanation, no markdown.
Example valid response: ["Artist", "Album"]
"""

    reply = call_llm([{"role": "user", "content": prompt}])
    return _parse_json_list(reply, valid_names=table_descriptions.keys())


def _parse_json_list(text, valid_names):
    """
    LLMs sometimes wrap JSON in ```json fences or add stray words.
    This pulls out the first [...] block and parses it safely.
    """
    match = re.search(r"\[.*?\]", text, re.DOTALL)
    if not match:
        raise ValueError(f"Could not find a JSON list in the LLM's reply: {text!r}")

    tables = json.loads(match.group(0))
    # keep only names that are real tables, in case the model hallucinates one
    return [t for t in tables if t in valid_names]


# ---------------------------------------------------------------------------
# 4. STEP 3 - SQL generator
# ---------------------------------------------------------------------------

def generate_sql(question, tables, table_schemas=TABLE_SCHEMAS):
    """
    Asks the LLM to write ONE SQL query, given the question and the full
    column-level schema of just the relevant tables.
    Returns a clean SQL string (no markdown fences, no commentary).
    """
    schema_block = "\n".join(table_schemas[t] for t in tables if t in table_schemas)

    prompt = f"""You are a SQL expert working with Microsoft SQL Server (T-SQL syntax), \
using the Chinook sample database.

Here is the schema of the relevant tables:
{schema_block}

Question: "{question}"

Write ONE SQL query that answers this question.
Rules:
- Use Microsoft SQL Server / T-SQL syntax specifically.
- To limit the number of rows, use "SELECT TOP N ..." - never use LIMIT (that's SQLite/MySQL syntax and will fail in SQL Server).
- Use square brackets around any table/column name that could clash with a reserved word, e.g. [Name].
- Output ONLY the SQL query. No explanation, no markdown code fences, no comments.
- Use only the tables and columns shown above.
- End the query with a semicolon.
"""

    reply = call_llm([{"role": "user", "content": prompt}])
    return _clean_sql(reply)


def _clean_sql(text):
    """Strips ```sql fences or stray text the model might add around the query."""
    text = text.strip()
    text = re.sub(r"^```(sql)?", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


# ---------------------------------------------------------------------------
# 5. Quick manual test - run this file directly to try the pipeline
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    question = "Which artist has the most albums?"

    print(f"Question: {question}\n")

    tables = relevant_tables(question)
    print(f"Step 2 - relevant tables: {tables}\n")

    sql = generate_sql(question, tables)
    print(f"Step 3 - generated SQL:\n{sql}")

    # NOTE: running the SQL against the real database is your teammate's
    # job (Step 4, via MCP Toolbox's execute_sql). This file stops here.