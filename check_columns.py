
import pandas as pd
import re
from urllib.parse import urlparse

# Change this to your exact CSV filename
INPUT_FILE = "historical_projects_ 4.csv"

EXPECTED_COLUMNS = [
    "project_id",
    "title",
    "abstract",
    "tech_stack",
    "domain",
    "source_type",
    "source_url",
    "year"
]

# Load dataset
try:
    df = pd.read_csv(INPUT_FILE)
except FileNotFoundError:
    print("ERROR: CSV file not found.")
    print("Check INPUT_FILE and the CSV filename.")
    raise SystemExit

print("\n========== DATASET SUMMARY ==========")
print("Total projects:", len(df))
print("Total columns:", len(df.columns))
print("Expected columns correct:",
      list(df.columns) == EXPECTED_COLUMNS)

print("\n========== MISSING VALUES ==========")
for col in df.columns:
    missing = (
        df[col].isna()
        | df[col].astype(str).str.strip().eq("")
    ).sum()
    print(f"{col}: {missing} missing values")

print("\n========== DUPLICATES ==========")

print("Duplicate project IDs:",
      df["project_id"].duplicated().sum())

normalized_titles = (
    df["title"].fillna("")
    .astype(str).str.lower().str.strip()
    .str.replace(r"\s+", " ", regex=True)
)

print("Duplicate titles:",
      normalized_titles.duplicated().sum())

print("\n========== SOURCE TYPES ==========")
print(df["source_type"].value_counts(dropna=False))

print("\n========== YEAR CHECK ==========")
years = pd.to_numeric(df["year"], errors="coerce")

print("Earliest year:", years.min())
print("Latest year:", years.max())

current_year = pd.Timestamp.now().year

invalid_years = df[
    years.isna() | (years < 1800) | (years > current_year)
]

print("Missing or suspicious years:", len(invalid_years))
invalid_years.to_csv("suspicious_years.csv", index=False)

print("\n========== TECHNOLOGY CHECK ==========")

def has_repeated_technology(value):
    if pd.isna(value):
        return False

    # Don't flag this explanatory placeholder
    if str(value).strip().lower() == (
        "not specified in cited official source"
    ):
        return False

    items = [
        item.strip().lower()
        for item in str(value).split(",")
        if item.strip()
    ]

    return len(items) != len(set(items))

repeated_tech = df[
    df["tech_stack"].apply(has_repeated_technology)
]

print("Rows with repeated technologies:", len(repeated_tech))
repeated_tech.to_csv("repeated_tech_stack_rows.csv", index=False)

print("\n========== URL FORMAT CHECK ==========")

def valid_url_format(value):
    if pd.isna(value):
        return False

    try:
        parsed = urlparse(str(value).strip())
        return (
            parsed.scheme in ("http", "https")
            and bool(parsed.netloc)
            and " " not in str(value).strip()
        )
    except ValueError:
        return False

bad_urls = df[~df["source_url"].apply(valid_url_format)]

print("Missing or malformed URLs:", len(bad_urls))
bad_urls.to_csv("check_source_urls.csv", index=False)

print("\n========== DOMAIN CHECK ==========")
print(df["domain"].value_counts(dropna=False))

print("\n========== FINAL RESULT ==========")
print("Original dataset has NOT been modified.")
print("Review the generated CSV reports before editing records.")
print("Check complete!")
