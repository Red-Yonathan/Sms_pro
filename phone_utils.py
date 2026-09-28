"""
phone_utils.py
================
Pure-Python helpers for cleaning, validating and extracting phone numbers
from the file formats the app supports: .txt, .json, .csv, .xlsx/.xls.

Nothing here imports Qt, so it can be unit-tested or reused by dialogs
(e.g. the Excel column picker) without pulling in the whole GUI.
"""
import os
import re
import ast
import json
import pandas as pd

SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".json", ".txt"}

# Column-name hints used to auto-detect a phone-number column in a
# spreadsheet. Checked in order: exact (case-insensitive) match first,
# then "contains" match.
PHONE_EXACT_HINTS = (
    "phone_number", "phone number", "phonenumber", "phone",
    "mobile_number", "mobile number", "mobilenumber", "mobile",
    "telephone", "tel", "msisdn", "contact_number", "contact number",
)
PHONE_CONTAINS_HINTS = ("phone", "mobile", "telephone", "msisdn", "number", "contact")


# ------------------------------------------------------------------ #
# Basic cleaning / validation
# ------------------------------------------------------------------ #
def clean_phone(value):
    return re.sub(r"[\s\-()]+", "", str(value).strip())


def valid_phone(value):
    value = clean_phone(value)
    digits = value.replace("+", "")
    return bool(value) and digits.isdigit() and 9 <= len(digits) <= 15


def parse_manual_phones(text):
    result = set()
    for token in re.split(r"[,\s;/\\\n]+", text.strip()):
        token = clean_phone(token)
        if valid_phone(token):
            result.add(token)
    return sorted(result)


def _dict_keys_type():
    return type({}.keys())


def extract_phones_from_data(data):
    """Handles both supported JSON shapes:
    - a flat list/array of phone numbers
    - {"phone": {"<number>": {...}, ...}, "total": {...}}
    Anything empty/blank along the way is skipped, never raised.
    """
    phones = set()
    if isinstance(data, (list, tuple, set)):
        values = data
    elif isinstance(data, dict):
        values = data.get("phone", data.get("phones", data.get("phone_numbers", [])))
        if isinstance(values, dict):
            values = values.keys()
        elif not isinstance(values, (list, tuple, set)):
            values = [values] if values else []
    else:
        values = []
    if not isinstance(values, (list, tuple, set, _dict_keys_type())):
        values = []
    for value in values:
        if value is None or str(value).strip() == "":
            continue
        value = clean_phone(value)
        if valid_phone(value):
            phones.add(value)
    return sorted(phones)


# ------------------------------------------------------------------ #
# Excel/CSV column detection
# ------------------------------------------------------------------ #
def detect_phone_column(columns):
    """Best-effort guess at which column holds phone numbers.
    Returns the original column label, or None if nothing looks right.
    """
    lowered = {col: str(col).strip().lower() for col in columns}
    for col, low in lowered.items():
        if low in PHONE_EXACT_HINTS:
            return col
    for col, low in lowered.items():
        if any(hint in low for hint in PHONE_CONTAINS_HINTS):
            return col
    return None


def truncate_cell(value, limit=15):
    """Shorten a preview cell to `limit` chars, appending '...' if cut."""
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value)
    return text if len(text) <= limit else text[:limit] + "..."


# ------------------------------------------------------------------ #
# Per-format readers
# ------------------------------------------------------------------ #
def parse_txt_file(filepath):
    phones = set()
    with open(filepath, "r", encoding="utf-8-sig", errors="ignore") as f:
        for line in f:
            for token in re.split(r"[,\s;/\\]+", line):
                token = clean_phone(token)
                if valid_phone(token):
                    phones.add(token)
    return sorted(phones)


def parse_json_file(filepath):
    with open(filepath, "r", encoding="utf-8-sig") as f:
        content = f.read().strip()
    if not content:
        return []
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        data = ast.literal_eval(content)
    return extract_phones_from_data(data)


def _read_table(filepath):
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".csv":
        try:
            return pd.read_csv(filepath, dtype=str, encoding="utf-8-sig")
        except UnicodeDecodeError:
            return pd.read_csv(filepath, dtype=str, encoding="cp1252")
    return pd.read_excel(filepath, dtype=str)


def read_table_preview(filepath, n_rows=5):
    """Reads just enough of a spreadsheet to preview it (used by the
    Excel column-picker dialog). Raises on unreadable files -- callers
    should catch and log."""
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".csv":
        try:
            return pd.read_csv(filepath, dtype=str, encoding="utf-8-sig", nrows=n_rows)
        except UnicodeDecodeError:
            return pd.read_csv(filepath, dtype=str, encoding="cp1252", nrows=n_rows)
    return pd.read_excel(filepath, dtype=str, nrows=n_rows)


def parse_table_file(filepath, column_override=None):
    df = _read_table(filepath)
    if df.empty or len(df.columns) == 0:
        return []
    if column_override and column_override in df.columns:
        phone_col = column_override
    else:
        phone_col = detect_phone_column(df.columns) or df.columns[0]
    phones = set()
    for value in df[phone_col].dropna().astype(str):
        if value.strip() == "":
            continue
        value = clean_phone(value)
        if valid_phone(value):
            phones.add(value)
    return sorted(phones)


def parse_phone_file(filepath, column_override=None):
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".txt":
        return parse_txt_file(filepath)
    if ext == ".json":
        return parse_json_file(filepath)
    if ext in (".csv", ".xlsx", ".xls"):
        return parse_table_file(filepath, column_override=column_override)
    return []
