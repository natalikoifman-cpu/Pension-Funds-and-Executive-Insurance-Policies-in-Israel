"""
Israeli Pension Fund and Executive Insurance Data API Client

A Python client for querying Israeli pension funds and executive insurance policies
(ביטוחי מנהלים) data from the government data repository.

API Base URL: https://fundscomparisonapi.azurewebsites.net
"""

import requests
import json
from typing import Optional, List, Dict, Any, Literal
from dataclasses import dataclass
from enum import Enum


BASE_URL = "https://fundscomparisonapi.azurewebsites.net"
ENDPOINT = "/api/Fundsnet/898dd1cf-3a25-49fd-8fd4-6c287bb654d1/funds"


class FundType(str, Enum):
    """Available fund types."""
    PENSION = "Pension"
    INSURANCE = "Insurance"


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
    - PARENT_COMPANY_ID: Parent company identifier
    - PARENT_COMPANY_NAME: Parent company name
    """
    # Mandatory fields
    FUND_ID = "FUND_ID"
    FUND_NAME = "FUND_NAME"
    PARENT_COMPANY_ID = "PARENT_COMPANY_ID"
    PARENT_COMPANY_NAME = "PARENT_COMPANY_NAME"

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

    # Additional filter/sort fields
    STOCK_MARKET_EXPOSURE_PERCENT = "STOCK_MARKET_EXPOSURE_PERCENT"
    FOREIGN_EXPOSURE_PERCENT = "FOREIGN_EXPOSURE_PERCENT"
    FOREIGN_CURRENCY_EXPOSURE_PERCENT = "FOREIGN_CURRENCY_EXPOSURE_PERCENT"
    NET_MONTHLY_DEPOSITS_PERCENT = "NET_MONTHLY_DEPOSITS_PERCENT"
    DEPOSITS_PERCENT = "DEPOSITS_PERCENT"
    WITHDRAWLS_PERCENT = "WITHDRAWLS_PERCENT"
    INTERNAL_TRANSFERS_PERCENT = "INTERNAL_TRANSFERS_PERCENT"


class PensionFundAPI:
    """Client for the Israeli Pension Fund Data API."""

    def __init__(self, base_url: str = BASE_URL, endpoint: str = ENDPOINT):
        """Initialize the API client.

        Args:
            base_url: API base URL
            endpoint: API endpoint path
        """
        self.base_url = base_url
        self.endpoint = endpoint

    def fetch_funds(
        self,
        fund_type: str = "Pension",
        fields: Optional[List[str]] = None,
        q: Optional[str] = None,
        sort: Optional[str] = None,
        limit: int = 10,
        offset: int = 0,
        distinct: bool = False,
        complex_filters: Optional[Dict[str, Any]] = None,
        months: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Fetch pension/insurance fund data from the Israeli funds API.

        Args:
            fund_type: "Pension" or "Insurance"
            fields: List of fields to return
            q: Text search query (comma-separated for AND logic)
            sort: Sort order, e.g., "YIELD_TRAILING_5_YRS desc nulls last"
            limit: Number of records (recommended: 5-10, max 20)
            offset: Pagination offset
            distinct: Return distinct records (must use with sort)
            complex_filters: Dict with filter operators ($gt, $lt, $gte, $lte, $eq, $neq, $in, $and, $or)
            months: Number of months to fetch (for historical data, use only for 1-2 funds)

        Returns:
            API response as dictionary

        Raises:
            requests.HTTPError: If the API request fails
            ValueError: If invalid parameters are provided
        """
        if fund_type not in ["Pension", "Insurance"]:
            raise ValueError(f"fund_type must be 'Pension' or 'Insurance', got '{fund_type}'")

        if distinct and not sort:
            raise ValueError("distinct=True requires a sort parameter")

        url = f"{self.base_url}{self.endpoint}/{fund_type}"

        params: Dict[str, Any] = {"limit": limit, "offset": offset}

        if fields:
            params["fields"] = ",".join(fields)
        if q:
            params["q"] = q
        if sort:
            params["sort"] = sort
        if distinct:
            params["distinct"] = "true"
        if complex_filters:
            params["complexFilters"] = json.dumps(complex_filters)
        if months:
            params["months"] = months

        response = requests.get(url, params=params)
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
            fund_type: "Pension" or "Insurance"
            years: Trailing years for yield (3 or 5)
            limit: Number of records to return

        Returns:
            API response with top performing funds
        """
        yield_field = f"YIELD_TRAILING_{years}_YRS"

        return self.fetch_funds(
            fund_type=fund_type,
            fields=[
                FundFields.FUND_ID,
                FundFields.FUND_NAME,
                FundFields.PARENT_COMPANY_NAME,
                yield_field,
                FundFields.AVG_ANNUAL_MANAGEMENT_FEE
            ],
            sort=f"{yield_field} desc nulls last",
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
            fund_type: "Pension" or "Insurance"
            limit: Number of records to return

        Returns:
            API response with low fee funds
        """
        return self.fetch_funds(
            fund_type=fund_type,
            fields=[
                FundFields.FUND_ID,
                FundFields.FUND_NAME,
                FundFields.PARENT_COMPANY_NAME,
                FundFields.AVG_ANNUAL_MANAGEMENT_FEE,
                FundFields.AVG_DEPOSIT_FEE,
                FundFields.YIELD_TRAILING_5_YRS
            ],
            sort=f"{FundFields.AVG_ANNUAL_MANAGEMENT_FEE} asc nulls last",
            limit=limit,
            distinct=True
        )

    def search_funds_by_text(
        self,
        search_terms: List[str],
        fund_type: str = "Pension",
        limit: int = 10
    ) -> Dict[str, Any]:
        """Search funds by text (AND logic).

        Args:
            search_terms: List of search terms (combined with AND logic)
            fund_type: "Pension" or "Insurance"
            limit: Number of records to return

        Returns:
            API response with matching funds
        """
        return self.fetch_funds(
            fund_type=fund_type,
            q=",".join(search_terms),
            limit=limit
        )

    def search_funds_by_age(
        self,
        age: int,
        fund_type: str = "Pension",
        limit: int = 10
    ) -> Dict[str, Any]:
        """Search for age-specific funds.

        Args:
            age: User age (will be rounded to nearest 10)
            fund_type: "Pension" or "Insurance"
            limit: Number of records to return

        Returns:
            API response with age-appropriate funds
        """
        # Round age to nearest 10
        rounded_age = round(age / 10) * 10

        return self.fetch_funds(
            fund_type=fund_type,
            q=f"{rounded_age},ומעלה",
            fields=[
                FundFields.FUND_ID,
                FundFields.FUND_NAME,
                FundFields.PARENT_COMPANY_NAME,
                FundFields.YIELD_TRAILING_3_YRS,
                FundFields.YIELD_TRAILING_5_YRS
            ],
            limit=limit
        )

    def get_high_exposure_funds(
        self,
        exposure_type: str = "STOCK_MARKET",
        min_percent: float = 50,
        fund_type: str = "Pension",
        limit: int = 10
    ) -> Dict[str, Any]:
        """Get funds with high market exposure.

        Args:
            exposure_type: Type of exposure (STOCK_MARKET, FOREIGN, or FOREIGN_CURRENCY)
            min_percent: Minimum exposure percentage
            fund_type: "Pension" or "Insurance"
            limit: Number of records to return

        Returns:
            API response with high exposure funds
        """
        exposure_field = f"{exposure_type}_EXPOSURE"
        filter_field = f"{exposure_type}_EXPOSURE_PERCENT"

        return self.fetch_funds(
            fund_type=fund_type,
            fields=[
                FundFields.FUND_ID,
                FundFields.FUND_NAME,
                FundFields.PARENT_COMPANY_NAME,
                exposure_field,
                FundFields.YIELD_TRAILING_5_YRS
            ],
            complex_filters={filter_field: {"$gte": min_percent}},
            sort=f"{filter_field} desc",
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
            fund_type: "Pension" or "Insurance"
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

        return self.fetch_funds(
            fund_type=fund_type,
            fields=[
                FundFields.FUND_ID,
                FundFields.FUND_NAME,
                FundFields.PARENT_COMPANY_NAME,
                FundFields.STANDARD_DEVIATION,
                FundFields.ALPHA,
                FundFields.SHARPE_RATIO,
                FundFields.YIELD_TRAILING_5_YRS
            ],
            sort=f"{sort_by} {sort_order} nulls last",
            limit=limit,
            distinct=True
        )

    def compare_funds(
        self,
        fund_ids: List[str],
        fund_type: str = "Pension",
        include_historical: bool = False,
        months: int = 12
    ) -> Dict[str, Any]:
        """Compare specific funds by their IDs.

        Args:
            fund_ids: List of fund IDs to compare
            fund_type: "Pension" or "Insurance"
            include_historical: Include historical data
            months: Number of months of historical data (only if include_historical=True)

        Returns:
            API response with fund comparison data
        """
        fields = [
            FundFields.FUND_ID,
            FundFields.FUND_NAME,
            FundFields.PARENT_COMPANY_NAME,
            FundFields.FUND_CLASSIFICATION,
            FundFields.TOTAL_ASSETS,
            FundFields.AVG_ANNUAL_MANAGEMENT_FEE,
            FundFields.AVG_DEPOSIT_FEE,
            FundFields.MONTHLY_YIELD,
            FundFields.YEAR_TO_DATE_YIELD,
            FundFields.YIELD_TRAILING_3_YRS,
            FundFields.YIELD_TRAILING_5_YRS,
            FundFields.STANDARD_DEVIATION,
            FundFields.SHARPE_RATIO,
            FundFields.STOCK_MARKET_EXPOSURE,
            FundFields.FOREIGN_EXPOSURE
        ]

        kwargs: Dict[str, Any] = {
            "fund_type": fund_type,
            "fields": fields,
            "complex_filters": {FundFields.FUND_ID: {"$in": fund_ids}},
            "limit": len(fund_ids)
        }

        if include_historical:
            kwargs["months"] = months

        return self.fetch_funds(**kwargs)

    def get_funds_by_company(
        self,
        company_name: str,
        fund_type: str = "Pension",
        limit: int = 20
    ) -> Dict[str, Any]:
        """Get all funds from a specific company.

        Args:
            company_name: Company name to search for
            fund_type: "Pension" or "Insurance"
            limit: Number of records to return

        Returns:
            API response with company funds
        """
        return self.fetch_funds(
            fund_type=fund_type,
            q=company_name,
            fields=[
                FundFields.FUND_ID,
                FundFields.FUND_NAME,
                FundFields.PARENT_COMPANY_NAME,
                FundFields.FUND_CLASSIFICATION,
                FundFields.AVG_ANNUAL_MANAGEMENT_FEE,
                FundFields.YIELD_TRAILING_5_YRS
            ],
            sort=f"{FundFields.YIELD_TRAILING_5_YRS} desc nulls last",
            limit=limit
        )


# Module-level convenience functions for backward compatibility
def fetch_funds(
    fund_type: str = "Pension",
    fields: Optional[List[str]] = None,
    q: Optional[str] = None,
    sort: Optional[str] = None,
    limit: int = 10,
    offset: int = 0,
    distinct: bool = False,
    complex_filters: Optional[Dict[str, Any]] = None,
    months: Optional[int] = None
) -> Dict[str, Any]:
    """
    Fetch pension/insurance fund data from the Israeli funds API.

    Args:
        fund_type: "Pension" or "Insurance"
        fields: List of fields to return
        q: Text search query (comma-separated for AND)
        sort: Sort order, e.g., "YIELD_TRAILING_5_YRS desc nulls last"
        limit: Number of records (recommended: 5-10)
        offset: Pagination offset
        distinct: Return distinct records (must use with sort)
        complex_filters: Dict with filter operators
        months: Number of months to fetch (for historical data)

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
        complex_filters=complex_filters,
        months=months
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
    search_terms: List[str],
    fund_type: str = "Pension",
    limit: int = 10
) -> Dict[str, Any]:
    """Search funds by text (AND logic)."""
    api = PensionFundAPI()
    return api.search_funds_by_text(search_terms=search_terms, fund_type=fund_type, limit=limit)


def get_high_exposure_funds(
    exposure_type: str = "STOCK_MARKET",
    min_percent: float = 50,
    fund_type: str = "Pension",
    limit: int = 10
) -> Dict[str, Any]:
    """Get funds with high market exposure."""
    api = PensionFundAPI()
    return api.get_high_exposure_funds(
        exposure_type=exposure_type,
        min_percent=min_percent,
        fund_type=fund_type,
        limit=limit
    )


if __name__ == "__main__":
    # Example usage
    api = PensionFundAPI()

    print("Top 5 Pension Funds by 5-Year Performance:")
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
