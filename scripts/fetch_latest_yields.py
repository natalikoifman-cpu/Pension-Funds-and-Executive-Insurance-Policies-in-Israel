#!/usr/bin/env python3
"""
Fetch Latest Yields from PensionNet and BituachNet APIs

This script pulls the most recent yield data from both pension and insurance
fund endpoints, normalizes the fields, and outputs a unified CSV.

Data Sources:
- PensionNet: Pension funds
- BituachNet: Insurance funds

Usage:
    python fetch_latest_yields.py [--output PATH] [--limit N]

Requirements:
    pip install requests pandas
"""

import argparse
import json
import sys
import time
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlencode, quote

import pandas as pd
import requests


# =============================================================================
# CONFIGURATION
# =============================================================================

# data.gov.il CKAN API (Israel government open data portal)
BASE_URL = "https://data.gov.il/api/3/action/datastore_search"

# Resource IDs for each fund type (2024-present daily data)
RESOURCE_IDS = {
    "pension": "6d47d6b5-cb08-488b-b333-f1e717b1e1bd",
    "insurance": "c6c62cc7-fe02-4b18-8f3e-813abfbb4647",
}

# Endpoints (CKAN uses resource_id, not path-based routing)
ENDPOINTS = {
    "pension": BASE_URL,
    "insurance": BASE_URL,
}

# Field mappings: API field name -> normalized name
# The API may use different field names, so we try multiple options
YIELD_FIELD_MAPPINGS = {
    "yield_12m": [
        "YEAR_TO_DATE_YIELD",
        "YIELD_TRAILING_12_MO",
        "TSUA_MITZ_LE_TKUFA",
        "TSUA_NOMINALIT_BRUTO_12_HODASHIM",
    ],
    "yield_3y": [
        "YIELD_TRAILING_3_YRS",
        "AVG_ANNUAL_YIELD_TRAILING_3YRS",
        "AVG_ANNUAL_YIELD_3_YRS",
        "TSUA_SHNATIT_MEMUZAAT_3_SHANIM",
    ],
    "yield_5y": [
        "YIELD_TRAILING_5_YRS",
        "AVG_ANNUAL_YIELD_TRAILING_5YRS",
        "AVG_ANNUAL_YIELD_5_YRS",
        "TSUA_SHNATIT_MEMUZAAT_5_SHANIM",
    ],
}

# Fields to request from API
REQUEST_FIELDS = [
    "FUND_ID",
    "FUND_NAME",
    "PARENT_COMPANY_ID",
    "PARENT_COMPANY_NAME",
    "REPORT_PERIOD",
    "YEAR_TO_DATE_YIELD",
    "YIELD_TRAILING_3_YRS",
    "YIELD_TRAILING_5_YRS",
    "AVG_ANNUAL_YIELD_3_YRS",
    "AVG_ANNUAL_YIELD_5_YRS",
    "MONTHLY_YIELD",
]

# Retry configuration
MAX_RETRIES = 4
INITIAL_BACKOFF = 2  # seconds


# =============================================================================
# HTTP CLIENT WITH RETRY
# =============================================================================

def make_request(
    url: str,
    params: Optional[Dict] = None,
    max_retries: int = MAX_RETRIES,
    initial_backoff: float = INITIAL_BACKOFF
) -> requests.Response:
    """
    Make HTTP GET request with exponential backoff retry.

    Args:
        url: The URL to request
        params: Query parameters
        max_retries: Maximum number of retry attempts
        initial_backoff: Initial backoff time in seconds

    Returns:
        Response object

    Raises:
        requests.HTTPError: If request fails after all retries
    """
    headers = {
        "Accept": "application/json",
    }

    backoff = initial_backoff

    for attempt in range(max_retries + 1):
        try:
            response = requests.get(url, params=params, headers=headers, timeout=60)

            # Check for rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", backoff))
                print(f"  Rate limited. Waiting {retry_after}s...")
                time.sleep(retry_after)
                backoff *= 2
                continue

            # Check for server errors (5xx)
            if response.status_code >= 500:
                if attempt < max_retries:
                    print(f"  Server error {response.status_code}. Retrying in {backoff}s...")
                    time.sleep(backoff)
                    backoff *= 2
                    continue

            response.raise_for_status()
            return response

        except requests.exceptions.Timeout:
            if attempt < max_retries:
                print(f"  Request timeout. Retrying in {backoff}s...")
                time.sleep(backoff)
                backoff *= 2
                continue
            raise

        except requests.exceptions.ConnectionError:
            if attempt < max_retries:
                print(f"  Connection error. Retrying in {backoff}s...")
                time.sleep(backoff)
                backoff *= 2
                continue
            raise

    raise requests.HTTPError(f"Request failed after {max_retries} retries")


# =============================================================================
# API DATA FETCHING
# =============================================================================

def get_latest_report_period(endpoint_url: str, source_name: str) -> str:
    """
    Determine the latest REPORT_PERIOD available for an endpoint.

    Args:
        endpoint_url: The API endpoint URL
        source_name: Name for logging ("pension" or "insurance")

    Returns:
        The latest REPORT_PERIOD as a string (e.g., "202312")
    """
    print(f"  Detecting latest REPORT_PERIOD for {source_name}...")

    params = {
        "resource_id": RESOURCE_IDS[source_name],
        "fields": "REPORT_PERIOD",
        "sort": "REPORT_PERIOD desc",
        "limit": 1,
    }

    response = make_request(endpoint_url, params)
    data = response.json()

    # Handle different response structures
    # API returns: {"success": true, "result": {"records": [...]}}
    records = []
    if isinstance(data, list):
        records = data
    elif isinstance(data, dict):
        # Check for nested result.records structure (data.gov.il API)
        if "result" in data and isinstance(data["result"], dict):
            records = data["result"].get("records", [])
        elif "records" in data:
            records = data["records"]
        else:
            # Try other common keys
            records = data.get("data", data.get("items", data.get("results", [])))

        if not records and "REPORT_PERIOD" in data:
            records = [data]

    if not records:
        raise ValueError(f"No data returned from {source_name} endpoint")

    # Extract REPORT_PERIOD from first record
    first_record = records[0]
    report_period = first_record.get("REPORT_PERIOD")

    if not report_period:
        # Try alternative field names
        for key in first_record:
            if "PERIOD" in key.upper() or "DATE" in key.upper():
                report_period = first_record[key]
                break

    if not report_period:
        raise ValueError(f"Could not find REPORT_PERIOD in {source_name} response")

    print(f"    Latest period: {report_period}")
    return str(report_period)


def fetch_all_funds(
    endpoint_url: str,
    source_name: str,
    limit: int = 1000
) -> Tuple[str, List[Dict]]:
    """
    Fetch all funds data from an endpoint.

    The API returns current/latest data, so no period filtering needed.
    Implements pagination if needed.

    Args:
        endpoint_url: The API endpoint URL
        source_name: Name for logging
        limit: Number of records per request

    Returns:
        Tuple of (report_period, list of fund records)
    """
    print(f"  Fetching all {source_name} funds...")

    all_records = []
    offset = 0
    page = 1
    report_period = None

    while True:
        params = {
            "resource_id": RESOURCE_IDS[source_name],
            "limit": limit,
            "offset": offset,
        }

        response = make_request(endpoint_url, params)
        data = response.json()

        # Handle different response structures
        # API returns: {"success": true, "result": {"records": [...]}}
        records = []
        if isinstance(data, list):
            records = data
        elif isinstance(data, dict):
            # Check for nested result.records structure (data.gov.il API)
            if "result" in data and isinstance(data["result"], dict):
                records = data["result"].get("records", [])
            elif "records" in data:
                records = data["records"]
            else:
                records = data.get("data", data.get("items", data.get("results", [])))

            if not records and ("FUND_ID" in data or "FUND_NAME" in data):
                records = [data]

        if not records:
            break

        # Extract report period from first record
        if not report_period and records:
            report_period = str(records[0].get("REPORT_PERIOD", "unknown"))

        all_records.extend(records)
        print(f"    Page {page}: fetched {len(records)} records (total: {len(all_records)})")

        # Check if we got fewer records than limit (last page)
        if len(records) < limit:
            break

        offset += limit
        page += 1

        # Safety limit to prevent infinite loops
        if page > 100:
            print("    Warning: Reached page limit (100), stopping pagination")
            break

    print(f"    Total {source_name} funds: {len(all_records)}")
    print(f"    Report period: {report_period}")
    return report_period, all_records


def discover_available_fields(endpoint_url: str, source_name: str) -> List[str]:
    """
    Discover what fields are available in the API response.

    Args:
        endpoint_url: The API endpoint URL
        source_name: Name for logging

    Returns:
        List of available field names
    """
    print(f"  Discovering available fields for {source_name}...")

    params = {
        "resource_id": RESOURCE_IDS[source_name],
        "limit": 1,
    }

    response = make_request(endpoint_url, params)
    data = response.json()

    records = []
    if isinstance(data, list):
        records = data
    elif isinstance(data, dict):
        # Check for nested result.records structure (data.gov.il API)
        if "result" in data and isinstance(data["result"], dict):
            records = data["result"].get("records", [])
        elif "records" in data:
            records = data["records"]
        else:
            records = data.get("data", data.get("items", data.get("results", [data])))

    if records:
        fields = list(records[0].keys())
        print(f"    Found {len(fields)} fields: {', '.join(sorted(fields)[:10])}...")
        return fields

    return []


# =============================================================================
# DATA NORMALIZATION
# =============================================================================

def parse_numeric(value) -> Optional[float]:
    """
    Parse a numeric value, handling various formats.

    Args:
        value: The value to parse (string, int, float, or None)

    Returns:
        Float value or None if parsing fails
    """
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):
        value = value.strip()
        if not value or value.lower() in ("null", "none", "n/a", "-"):
            return None

        # Remove percentage sign and whitespace
        value = value.replace("%", "").replace(",", ".").strip()

        try:
            return float(value)
        except ValueError:
            return None

    return None


def find_field_value(record: Dict, field_candidates: List[str]) -> Optional[float]:
    """
    Find a field value by trying multiple possible field names.

    Args:
        record: The data record
        field_candidates: List of possible field names to try

    Returns:
        The parsed numeric value or None
    """
    for field_name in field_candidates:
        if field_name in record:
            value = parse_numeric(record[field_name])
            if value is not None:
                return value

        # Try case-insensitive match
        for key in record:
            if key.upper() == field_name.upper():
                value = parse_numeric(record[key])
                if value is not None:
                    return value

    return None


def normalize_records(records: List[Dict], source: str, report_period: str) -> List[Dict]:
    """
    Normalize fund records to unified schema.

    Args:
        records: Raw API records
        source: Source name ("pension" or "insurance")
        report_period: The report period

    Returns:
        List of normalized records
    """
    normalized = []

    for record in records:
        # Extract fund identifiers
        fund_id = record.get("FUND_ID") or record.get("fund_id") or record.get("ID")
        fund_name = record.get("FUND_NAME") or record.get("fund_name") or record.get("NAME")

        # Extract parent company info
        parent_company_id = (
            record.get("PARENT_COMPANY_ID") or
            record.get("parent_company_id") or
            record.get("MANAGING_COMPANY_ID")
        )
        parent_company_name = (
            record.get("PARENT_COMPANY_NAME") or
            record.get("parent_company_name") or
            record.get("MANAGING_COMPANY")
        )

        # Extract yields using field mappings
        yield_12m = find_field_value(record, YIELD_FIELD_MAPPINGS["yield_12m"])
        yield_3y = find_field_value(record, YIELD_FIELD_MAPPINGS["yield_3y"])
        yield_5y = find_field_value(record, YIELD_FIELD_MAPPINGS["yield_5y"])

        normalized.append({
            "source": source,
            "report_period": report_period,
            "fund_id": fund_id,
            "fund_name": fund_name,
            "parent_company_id": parent_company_id,
            "parent_company_name": parent_company_name,
            "yield_12m": yield_12m,
            "yield_3y": yield_3y,
            "yield_5y": yield_5y,
        })

    return normalized


# =============================================================================
# MAIN PROCESSING
# =============================================================================

def fetch_source_data(source: str, limit: int = 1000) -> Tuple[str, pd.DataFrame]:
    """
    Fetch and normalize data for a single source.

    Args:
        source: Source name ("pension" or "insurance")
        limit: Records per page

    Returns:
        Tuple of (report_period, DataFrame)
    """
    endpoint_url = ENDPOINTS[source]

    print(f"\n{'='*60}")
    print(f"Processing {source.upper()} funds")
    print(f"{'='*60}")

    # Fetch all funds (API returns current/latest data)
    report_period, records = fetch_all_funds(endpoint_url, source, limit)

    if not records:
        print(f"  Warning: No records fetched for {source}")
        return report_period or "unknown", pd.DataFrame()

    # Normalize records
    normalized = normalize_records(records, source, report_period or "unknown")

    # Convert to DataFrame
    df = pd.DataFrame(normalized)

    return report_period or "unknown", df


def print_summary(df: pd.DataFrame, source: str, report_period: str) -> None:
    """
    Print summary statistics for a source.

    Args:
        df: DataFrame with fund data
        source: Source name
        report_period: Report period
    """
    if df.empty or "source" not in df.columns:
        print(f"\n{source.upper()} Summary:")
        print(f"  Report Period: {report_period}")
        print(f"  Total Funds: 0")
        return

    source_df = df[df["source"] == source]

    print(f"\n{source.upper()} Summary:")
    print(f"  Report Period: {report_period}")
    print(f"  Total Funds: {len(source_df)}")

    # Count non-null yields
    yield_12m_count = source_df["yield_12m"].notna().sum()
    yield_3y_count = source_df["yield_3y"].notna().sum()
    yield_5y_count = source_df["yield_5y"].notna().sum()

    print(f"  Funds with yield_12m: {yield_12m_count}")
    print(f"  Funds with yield_3y: {yield_3y_count}")
    print(f"  Funds with yield_5y: {yield_5y_count}")

    # Top 10 by yield_5y
    print(f"\n  Top 10 by 5-Year Yield (descending, nulls last):")
    top_10 = source_df.dropna(subset=["yield_5y"]).nlargest(10, "yield_5y")

    if top_10.empty:
        print("    No funds with yield_5y data")
    else:
        for i, (_, row) in enumerate(top_10.iterrows(), 1):
            name = row["fund_name"][:40] if row["fund_name"] else "N/A"
            yield_val = row["yield_5y"]
            print(f"    {i:2}. {name:<40} {yield_val:>8.2f}%")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Fetch latest yields from PensionNet and BituachNet APIs"
    )
    parser.add_argument(
        "--output",
        default="latest_yields_unified.csv",
        help="Output CSV file path (default: latest_yields_unified.csv)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1000,
        help="Records per API request (default: 1000)"
    )
    parser.add_argument(
        "--discover-fields",
        action="store_true",
        help="Discover and print available API fields"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("  FETCH LATEST YIELDS FROM PENSION & INSURANCE APIs")
    print("=" * 60)
    print(f"Output file: {args.output}")
    print(f"Records per request: {args.limit}")

    # Optional: discover fields
    if args.discover_fields:
        print("\nDiscovering API fields...")
        for source, endpoint in ENDPOINTS.items():
            fields = discover_available_fields(endpoint, source)
            print(f"\n{source.upper()} fields:")
            for f in sorted(fields):
                print(f"  - {f}")
        return 0

    # Fetch data from both sources
    all_dfs = []
    periods = {}

    for source in ["pension", "insurance"]:
        try:
            report_period, df = fetch_source_data(source, args.limit)
            periods[source] = report_period
            all_dfs.append(df)
        except Exception as e:
            print(f"\nError fetching {source} data: {e}")
            import traceback
            traceback.print_exc()
            continue

    if not all_dfs:
        print("\nNo data fetched from any source!")
        return 1

    # Combine all data
    print("\n" + "=" * 60)
    print("COMBINING DATA")
    print("=" * 60)

    unified_df = pd.concat(all_dfs, ignore_index=True)
    print(f"Total unified records: {len(unified_df)}")

    # Save to CSV
    unified_df.to_csv(args.output, index=False, encoding="utf-8-sig")
    print(f"\nSaved to: {args.output}")

    # Print summaries
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    for source in ["pension", "insurance"]:
        if source in periods:
            print_summary(unified_df, source, periods[source])

    # Overall statistics
    print("\n" + "-" * 60)
    print("OVERALL:")
    print(f"  Total funds: {len(unified_df)}")
    print(f"  Pension funds: {len(unified_df[unified_df['source'] == 'pension'])}")
    print(f"  Insurance funds: {len(unified_df[unified_df['source'] == 'insurance'])}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
