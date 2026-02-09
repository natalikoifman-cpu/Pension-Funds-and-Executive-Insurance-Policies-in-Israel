"""
Israeli Pension Fund and Executive Insurance Data API Client

A Python client for querying Israeli pension funds, executive insurance policies
(ביטוחי מנהלים), and provident funds (קופות גמל) data from data.gov.il,
the official Israeli government open data portal (CKAN API).

API Base URL: https://data.gov.il/api/3/action/datastore_search
"""

import requests
import json
from typing import Optional, List, Dict, Any, Literal
from dataclasses import dataclass
from enum import Enum


BASE_URL = "https://data.gov.il/api/3/action/datastore_search"

# Resource IDs for each fund type (2024-present daily data)
RESOURCE_IDS = {
    "Pension": "6d47d6b5-cb08-488b-b333-f1e717b1e1bd",
    "Insurance": "c6c62cc7-fe02-4b18-8f3e-813abfbb4647",
    "Provident": "a30dcbea-a1d2-482c-ae29-8f781f5025fb",
}


class FundType(str, Enum):
    """Available fund types."""
    PENSION = "Pension"
    INSURANCE = "Insurance"
    PROVIDENT = "Provident"


class ExposureType(str, Enum):
    """Available exposure types for filtering."""
    STOCK_MARKET = "STOCK_MARKET"
    FOREIGN = "FOREIGN"
    FOREIGN_CURRENCY = "FOREIGN_CURRENCY"


@dataclass
class FundFields:
    """Available fields for fund data queries.

    Mandatory fields (always included):
    - FUND_ID: Unique fund identifier
    - FUND_NAME: Fund name
    """
    # Mandatory fields
    FUND_ID = "FUND_ID"
    FUND_NAME = "FUND_NAME"

    # Company fields (Pension/Insurance datasets)
    PARENT_COMPANY_ID = "PARENT_COMPANY_ID"
    PARENT_COMPANY_NAME = "PARENT_COMPANY_NAME"

    # Company fields (Provident/Gemel dataset)
    MANAGING_CORPORATION = "MANAGING_CORPORATION"
    CONTROLLING_CORPORATION = "CONTROLLING_CORPORATION"

    # Classification and reporting
    FUND_CLASSIFICATION = "FUND_CLASSIFICATION"
    REPORT_PERIOD = "REPORT_PERIOD"

    # Assets and fees
    TOTAL_ASSETS = "TOTAL_ASSETS"
    AVG_ANNUAL_MANAGEMENT_FEE = "AVG_ANNUAL_MANAGEMENT_FEE"
    AVG_DEPOSIT_FEE = "AVG_DEPOSIT_FEE"

    # Yield metrics
    MONTHLY_YIELD = "MONTHLY_YIELD"
    YEAR_TO_DATE_YIELD = "YEAR_TO_DATE_YIELD"
    YIELD_TRAILING_3_YRS = "YIELD_TRAILING_3_YRS"
    YIELD_TRAILING_5_YRS = "YIELD_TRAILING_5_YRS"
    AVG_ANNUAL_YIELD_TRAILING_3YRS = "AVG_ANNUAL_YIELD_TRAILING_3YRS"
    AVG_ANNUAL_YIELD_TRAILING_5YRS = "AVG_ANNUAL_YIELD_TRAILING_5YRS"

    # Risk metrics
    STANDARD_DEVIATION = "STANDARD_DEVIATION"
    ALPHA = "ALPHA"
    SHARPE_RATIO = "SHARPE_RATIO"

    # Exposure metrics
    LIQUID_ASSETS_PERCENT = "LIQUID_ASSETS_PERCENT"
    STOCK_MARKET_EXPOSURE = "STOCK_MARKET_EXPOSURE"
    FOREIGN_EXPOSURE = "FOREIGN_EXPOSURE"
    FOREIGN_CURRENCY_EXPOSURE = "FOREIGN_CURRENCY_EXPOSURE"


class PensionFundAPI:
    """Client for the Israeli pension fund data via data.gov.il CKAN API."""

    def __init__(self, base_url: str = BASE_URL, resource_ids: Dict[str, str] = None):
        """Initialize the API client.

        Args:
            base_url: CKAN datastore_search endpoint URL
            resource_ids: Mapping of fund type to data.gov.il resource IDs
        """
        self.base_url = base_url
        self.resource_ids = resource_ids or RESOURCE_IDS

    def _get_resource_id(self, fund_type: str) -> str:
        """Get the data.gov.il resource ID for a fund type."""
        if fund_type in self.resource_ids:
            return self.resource_ids[fund_type]
        raise ValueError(
            f"Unknown fund_type '{fund_type}'. "
            f"Valid types: {list(self.resource_ids.keys())}"
        )

    def fetch_funds(
        self,
        fund_type: str = "Pension",
        fields: Optional[List[str]] = None,
        q: Optional[str] = None,
        sort: Optional[str] = None,
        limit: int = 10,
        offset: int = 0,
        distinct: bool = False,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Fetch pension/insurance/provident fund data from data.gov.il.

        Args:
            fund_type: "Pension", "Insurance", or "Provident"
            fields: List of fields to return
            q: Text search query
            sort: Sort order, e.g., "YIELD_TRAILING_5_YRS desc"
            limit: Number of records (default: 10)
            offset: Pagination offset
            distinct: Return distinct records
            filters: Dict of exact-match filters, e.g. {"FUND_CLASSIFICATION": "קרנות השתלמות"}

        Returns:
            API response as dictionary with {success, result: {records, total}}
        """
        resource_id = self._get_resource_id(fund_type)

        if distinct and not sort:
            raise ValueError("distinct=True requires a sort parameter")

        params: Dict[str, Any] = {
            "resource_id": resource_id,
            "limit": limit,
            "offset": offset,
            "include_total": True,
        }

        if fields:
            params["fields"] = ",".join(fields)
        if q:
            params["q"] = q
        if sort:
            params["sort"] = sort
        if distinct:
            params["distinct"] = "true"
        if filters:
            params["filters"] = json.dumps(filters)

        response = requests.get(self.base_url, params=params)
        response.raise_for_status()

        return response.json()

    def get_top_performing_funds(
        self,
        fund_type: str = "Pension",
        years: Literal[3, 5] = 5,
        limit: int = 10
    ) -> Dict[str, Any]:
        """Get top performing funds by trailing yield.

        Args:
            fund_type: "Pension", "Insurance", or "Provident"
            years: Trailing years for yield (3 or 5)
            limit: Number of records to return

        Returns:
            API response with top performing funds
        """
        yield_field = f"YIELD_TRAILING_{years}_YRS"

        # Use MANAGING_CORPORATION for Provident, PARENT_COMPANY_NAME for others
        company_field = (
            FundFields.MANAGING_CORPORATION if fund_type == "Provident"
            else FundFields.PARENT_COMPANY_NAME
        )

        return self.fetch_funds(
            fund_type=fund_type,
            fields=[
                FundFields.FUND_ID,
                FundFields.FUND_NAME,
                company_field,
                yield_field,
                FundFields.AVG_ANNUAL_MANAGEMENT_FEE
            ],
            sort=f"{yield_field} desc",
            limit=limit,
            distinct=True
        )

    def get_low_fee_funds(
        self,
        fund_type: str = "Pension",
        limit: int = 10
    ) -> Dict[str, Any]:
        """Get funds with lowest management fees.

        Args:
            fund_type: "Pension", "Insurance", or "Provident"
            limit: Number of records to return

        Returns:
            API response with low fee funds
        """
        company_field = (
            FundFields.MANAGING_CORPORATION if fund_type == "Provident"
            else FundFields.PARENT_COMPANY_NAME
        )

        return self.fetch_funds(
            fund_type=fund_type,
            fields=[
                FundFields.FUND_ID,
                FundFields.FUND_NAME,
                company_field,
                FundFields.AVG_ANNUAL_MANAGEMENT_FEE,
                FundFields.AVG_DEPOSIT_FEE,
                FundFields.YIELD_TRAILING_5_YRS
            ],
            sort=f"{FundFields.AVG_ANNUAL_MANAGEMENT_FEE} asc",
            limit=limit,
            distinct=True
        )

    def search_funds_by_text(
        self,
        search_text: str,
        fund_type: str = "Pension",
        limit: int = 10
    ) -> Dict[str, Any]:
        """Search funds by text.

        Args:
            search_text: Search text
            fund_type: "Pension", "Insurance", or "Provident"
            limit: Number of records to return

        Returns:
            API response with matching funds
        """
        return self.fetch_funds(
            fund_type=fund_type,
            q=search_text,
            limit=limit
        )

    def get_funds_by_classification(
        self,
        classification: str,
        fund_type: str = "Provident",
        sort: str = "YEAR_TO_DATE_YIELD desc",
        limit: int = 10
    ) -> Dict[str, Any]:
        """Get funds filtered by FUND_CLASSIFICATION.

        Args:
            classification: Classification value, e.g. "קופת גמל להשקעה"
            fund_type: "Pension", "Insurance", or "Provident"
            sort: Sort order
            limit: Number of records to return

        Returns:
            API response with matching funds
        """
        return self.fetch_funds(
            fund_type=fund_type,
            filters={"FUND_CLASSIFICATION": classification},
            sort=sort,
            limit=limit,
            distinct=True
        )

    def get_high_exposure_funds(
        self,
        exposure_type: str = "STOCK_MARKET",
        fund_type: str = "Pension",
        limit: int = 10
    ) -> Dict[str, Any]:
        """Get funds sorted by market exposure (descending).

        Note: CKAN doesn't support range filters, so this sorts by exposure
        rather than filtering by minimum percentage.

        Args:
            exposure_type: Type of exposure (STOCK_MARKET, FOREIGN, or FOREIGN_CURRENCY)
            fund_type: "Pension", "Insurance", or "Provident"
            limit: Number of records to return

        Returns:
            API response with high exposure funds
        """
        exposure_field = f"{exposure_type}_EXPOSURE"

        company_field = (
            FundFields.MANAGING_CORPORATION if fund_type == "Provident"
            else FundFields.PARENT_COMPANY_NAME
        )

        return self.fetch_funds(
            fund_type=fund_type,
            fields=[
                FundFields.FUND_ID,
                FundFields.FUND_NAME,
                company_field,
                exposure_field,
                FundFields.YIELD_TRAILING_5_YRS
            ],
            sort=f"{exposure_field} desc",
            limit=limit
        )

    def get_funds_with_risk_metrics(
        self,
        fund_type: str = "Pension",
        sort_by: str = "SHARPE_RATIO",
        descending: bool = True,
        limit: int = 10
    ) -> Dict[str, Any]:
        """Get funds with risk metrics.

        Args:
            fund_type: "Pension", "Insurance", or "Provident"
            sort_by: Field to sort by (SHARPE_RATIO, ALPHA, STANDARD_DEVIATION)
            descending: Sort in descending order
            limit: Number of records to return

        Returns:
            API response with risk metrics

        Risk Metrics Explanation:
            - Standard Deviation: Measures fund volatility. Higher values = higher risk.
            - Alpha: Measures excess return vs. benchmark. Positive alpha = outperformance.
            - Sharpe Ratio: Risk-adjusted return. Higher = better return per unit of risk.
        """
        sort_order = "desc" if descending else "asc"

        company_field = (
            FundFields.MANAGING_CORPORATION if fund_type == "Provident"
            else FundFields.PARENT_COMPANY_NAME
        )

        return self.fetch_funds(
            fund_type=fund_type,
            fields=[
                FundFields.FUND_ID,
                FundFields.FUND_NAME,
                company_field,
                FundFields.STANDARD_DEVIATION,
                FundFields.ALPHA,
                FundFields.SHARPE_RATIO,
                FundFields.YIELD_TRAILING_5_YRS
            ],
            sort=f"{sort_by} {sort_order}",
            limit=limit,
            distinct=True
        )

    def get_funds_by_company(
        self,
        company_name: str,
        fund_type: str = "Pension",
        limit: int = 20
    ) -> Dict[str, Any]:
        """Get all funds from a specific company.

        Args:
            company_name: Company name to search for
            fund_type: "Pension", "Insurance", or "Provident"
            limit: Number of records to return

        Returns:
            API response with company funds
        """
        return self.fetch_funds(
            fund_type=fund_type,
            q=company_name,
            sort=f"{FundFields.YIELD_TRAILING_5_YRS} desc",
            limit=limit
        )


# Module-level convenience functions
def fetch_funds(
    fund_type: str = "Pension",
    fields: Optional[List[str]] = None,
    q: Optional[str] = None,
    sort: Optional[str] = None,
    limit: int = 10,
    offset: int = 0,
    distinct: bool = False,
    filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Fetch pension/insurance/provident fund data from data.gov.il.

    Args:
        fund_type: "Pension", "Insurance", or "Provident"
        fields: List of fields to return
        q: Text search query
        sort: Sort order, e.g., "YIELD_TRAILING_5_YRS desc"
        limit: Number of records (default: 10)
        offset: Pagination offset
        distinct: Return distinct records
        filters: Dict of exact-match filters

    Returns:
        API response as dictionary
    """
    api = PensionFundAPI()
    return api.fetch_funds(
        fund_type=fund_type,
        fields=fields,
        q=q,
        sort=sort,
        limit=limit,
        offset=offset,
        distinct=distinct,
        filters=filters,
    )


def get_top_performing_funds(
    fund_type: str = "Pension",
    years: int = 5,
    limit: int = 10
) -> Dict[str, Any]:
    """Get top performing funds by trailing yield."""
    api = PensionFundAPI()
    return api.get_top_performing_funds(fund_type=fund_type, years=years, limit=limit)


def get_low_fee_funds(
    fund_type: str = "Pension",
    limit: int = 10
) -> Dict[str, Any]:
    """Get funds with lowest management fees."""
    api = PensionFundAPI()
    return api.get_low_fee_funds(fund_type=fund_type, limit=limit)


def search_funds_by_text(
    search_text: str,
    fund_type: str = "Pension",
    limit: int = 10
) -> Dict[str, Any]:
    """Search funds by text."""
    api = PensionFundAPI()
    return api.search_funds_by_text(search_text=search_text, fund_type=fund_type, limit=limit)


def get_high_exposure_funds(
    exposure_type: str = "STOCK_MARKET",
    fund_type: str = "Pension",
    limit: int = 10
) -> Dict[str, Any]:
    """Get funds sorted by market exposure."""
    api = PensionFundAPI()
    return api.get_high_exposure_funds(
        exposure_type=exposure_type,
        fund_type=fund_type,
        limit=limit
    )


if __name__ == "__main__":
    # Example usage
    api = PensionFundAPI()

    print("Top 5 Pension Funds by 5-Year Performance (data.gov.il):")
    print("=" * 50)

    result = api.get_top_performing_funds(limit=5)

    if result.get("success"):
        records = result.get("result", {}).get("records", [])
        for i, fund in enumerate(records, 1):
            name = fund.get('FUND_NAME', 'N/A')
            company = fund.get('PARENT_COMPANY_NAME', 'N/A')
            yield_5yr = fund.get('YIELD_TRAILING_5_YRS', 'N/A')
            fee = fund.get('AVG_ANNUAL_MANAGEMENT_FEE', 'N/A')
            print(f"{i}. {name}")
            print(f"   Company: {company}")
            print(f"   5-Year Yield: {yield_5yr}%")
            print(f"   Management Fee: {fee}%")
            print()
    else:
        print("Failed to fetch data")
