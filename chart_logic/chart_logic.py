"""
chart_logic.py
Decides whether a SQL query result can be shown as a chart, and if so,
what type of chart and how to format the data for Chart.js on the frontend.
"""

import re

# Chinook's primary/foreign key columns are consistently PascalCase with a
# capital-I "Id" suffix (CustomerId, ArtistId, InvoiceId, ...). Matching
# case-sensitively avoids false positives on real measurement columns that
# happen to end in "id" as lowercase letters (e.g. "Paid").
_ID_COLUMN_SUFFIX = re.compile(r"Id$")


def suggest_chart(rows):
    """
    Looks at the shape of the query result and suggests a chart type.

    Parameters:
        rows (list[dict]): the actual result rows, e.g.
            [{"Genre": "Rock", "TotalSales": 200}, {"Genre": "Jazz", "TotalSales": 50}]
            Column names are read from the keys of the first row.

    Returns:
        dict: either {"type": None} if no chart makes sense, or
              {
                  "type": "bar" | "line" | "pie",
                  "x": <column used for labels>,
                  "y": <column used for values>,
                  "labels": [...],
                  "values": [...]
              }
    """

    # Not enough data to make a chart
    if not rows:
        return {"type": None}

    sample = rows[0]
    columns = list(sample.keys())

    if len(columns) < 2:
        return {"type": None}

    # Find which columns are text (good for labels) and which are numbers (good for values).
    # ID columns (CustomerId, ArtistId, ...) are numeric but are row identifiers,
    # not measurements - excluded so they can never be picked as the charted value.
    text_cols = [c for c in columns if isinstance(sample.get(c), str)]
    num_cols = [
        c for c in columns
        if isinstance(sample.get(c), (int, float)) and not _ID_COLUMN_SUFFIX.search(c)
    ]

    # We need at least one text column and one number column to draw a chart
    if not text_cols or not num_cols:
        return {"type": None}

    x_col = text_cols[0]   # first text column becomes the labels (x-axis)
    y_col = num_cols[0]    # first number column becomes the values (y-axis)

    # Decide chart type using simple rules
    date_keywords = ["date", "month", "year", "day"]
    if any(keyword in x_col.lower() for keyword in date_keywords):
        chart_type = "line"       # time-based data looks best as a line chart
    elif len(rows) <= 6:
        chart_type = "pie"        # small number of categories -> pie chart
    else:
        chart_type = "bar"        # everything else -> bar chart

    return {
        "type": chart_type,
        "x": x_col,
        "y": y_col,
        "labels": [row[x_col] for row in rows],
        "values": [row[y_col] for row in rows],
    }