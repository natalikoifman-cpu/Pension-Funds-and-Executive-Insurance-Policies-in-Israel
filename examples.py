"""
Example usage of the Israeli Pension Fund Data API Client.

This script demonstrates various queries and use cases for comparing
pension funds and executive insurance policies in Israel.
"""

from pension_fund_api import PensionFundAPI, FundFields, FundType


def print_separator(title: str) -> None:
    """Print a formatted section separator."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60 + "\n")


def format_percentage(value) -> str:
    """Format a value as percentage."""
    if value is None:
        return "N/A"
    try:
        return f"{float(value):.2f}%"
    except (ValueError, TypeError):
        return str(value)


def example_top_performing_funds():
    """Example: Get top performing pension funds by 5-year yield."""
    print_separator("Top 5 Pension Funds by 5-Year Performance")

    api = PensionFundAPI()
    result = api.get_top_performing_funds(fund_type="Pension", years=5, limit=5)

    if result.get("success"):
        records = result.get("result", {}).get("records", [])
        for i, fund in enumerate(records, 1):
            print(f"{i}. {fund.get('FUND_NAME', 'N/A')}")
            print(f"   Company: {fund.get('PARENT_COMPANY_NAME', 'N/A')}")
            print(f"   5-Year Yield: {format_percentage(fund.get('YIELD_TRAILING_5_YRS'))}")
            print(f"   Management Fee: {format_percentage(fund.get('AVG_ANNUAL_MANAGEMENT_FEE'))}")
            print()
    else:
        print("Failed to fetch data")


def example_low_fee_funds():
    """Example: Get funds with the lowest management fees."""
    print_separator("Top 5 Funds with Lowest Management Fees")

    api = PensionFundAPI()
    result = api.get_low_fee_funds(fund_type="Pension", limit=5)

    if result.get("success"):
        records = result.get("result", {}).get("records", [])
        for i, fund in enumerate(records, 1):
            print(f"{i}. {fund.get('FUND_NAME', 'N/A')}")
            print(f"   Company: {fund.get('PARENT_COMPANY_NAME', 'N/A')}")
            print(f"   Management Fee: {format_percentage(fund.get('AVG_ANNUAL_MANAGEMENT_FEE'))}")
            print(f"   Deposit Fee: {format_percentage(fund.get('AVG_DEPOSIT_FEE'))}")
            print(f"   5-Year Yield: {format_percentage(fund.get('YIELD_TRAILING_5_YRS'))}")
            print()
    else:
        print("Failed to fetch data")


def example_risk_metrics():
    """Example: Get funds with risk metrics, sorted by Sharpe Ratio."""
    print_separator("Top 5 Funds by Sharpe Ratio (Risk-Adjusted Performance)")

    api = PensionFundAPI()
    result = api.get_funds_with_risk_metrics(
        fund_type="Pension",
        sort_by="SHARPE_RATIO",
        descending=True,
        limit=5
    )

    if result.get("success"):
        records = result.get("result", {}).get("records", [])

        print("Risk Metrics Explanation:")
        print("-" * 40)
        print("- Sharpe Ratio: Higher = better return per unit of risk")
        print("- Alpha: Positive = outperforms benchmark")
        print("- Std Dev: Lower = less volatile")
        print()

        for i, fund in enumerate(records, 1):
            print(f"{i}. {fund.get('FUND_NAME', 'N/A')}")
            print(f"   Company: {fund.get('PARENT_COMPANY_NAME', 'N/A')}")
            print(f"   Sharpe Ratio: {fund.get('SHARPE_RATIO', 'N/A')}")
            print(f"   Alpha: {fund.get('ALPHA', 'N/A')}")
            print(f"   Std Deviation: {fund.get('STANDARD_DEVIATION', 'N/A')}")
            print(f"   5-Year Yield: {format_percentage(fund.get('YIELD_TRAILING_5_YRS'))}")
            print()
    else:
        print("Failed to fetch data")


def example_high_stock_exposure():
    """Example: Get funds with high stock market exposure."""
    print_separator("Funds with Stock Market Exposure >= 50%")

    api = PensionFundAPI()
    result = api.get_high_exposure_funds(
        exposure_type="STOCK_MARKET",
        min_percent=50,
        fund_type="Pension",
        limit=5
    )

    if result.get("success"):
        records = result.get("result", {}).get("records", [])
        for i, fund in enumerate(records, 1):
            print(f"{i}. {fund.get('FUND_NAME', 'N/A')}")
            print(f"   Company: {fund.get('PARENT_COMPANY_NAME', 'N/A')}")
            print(f"   Stock Exposure: {format_percentage(fund.get('STOCK_MARKET_EXPOSURE'))}")
            print(f"   5-Year Yield: {format_percentage(fund.get('YIELD_TRAILING_5_YRS'))}")
            print()
    else:
        print("Failed to fetch data")


def example_age_specific_funds():
    """Example: Search for age-specific funds (for age 60+)."""
    print_separator("Age-Specific Funds for 60+ Years Old")

    api = PensionFundAPI()
    result = api.search_funds_by_age(age=62, fund_type="Pension", limit=5)

    if result.get("success"):
        records = result.get("result", {}).get("records", [])
        if records:
            for i, fund in enumerate(records, 1):
                print(f"{i}. {fund.get('FUND_NAME', 'N/A')}")
                print(f"   Company: {fund.get('PARENT_COMPANY_NAME', 'N/A')}")
                print(f"   3-Year Yield: {format_percentage(fund.get('YIELD_TRAILING_3_YRS'))}")
                print(f"   5-Year Yield: {format_percentage(fund.get('YIELD_TRAILING_5_YRS'))}")
                print()
        else:
            print("No age-specific funds found")
    else:
        print("Failed to fetch data")


def example_insurance_funds():
    """Example: Get executive insurance policies (ביטוחי מנהלים)."""
    print_separator("Top 5 Executive Insurance Policies by YTD Performance")

    api = PensionFundAPI()
    result = api.fetch_funds(
        fund_type="Insurance",
        fields=[
            FundFields.FUND_ID,
            FundFields.FUND_NAME,
            FundFields.PARENT_COMPANY_NAME,
            FundFields.MONTHLY_YIELD,
            FundFields.YEAR_TO_DATE_YIELD,
            FundFields.SHARPE_RATIO
        ],
        sort=f"{FundFields.YEAR_TO_DATE_YIELD} desc nulls last",
        limit=5,
        distinct=True
    )

    if result.get("success"):
        records = result.get("result", {}).get("records", [])
        for i, fund in enumerate(records, 1):
            print(f"{i}. {fund.get('FUND_NAME', 'N/A')}")
            print(f"   Company: {fund.get('PARENT_COMPANY_NAME', 'N/A')}")
            print(f"   Monthly Yield: {format_percentage(fund.get('MONTHLY_YIELD'))}")
            print(f"   YTD Yield: {format_percentage(fund.get('YEAR_TO_DATE_YIELD'))}")
            print(f"   Sharpe Ratio: {fund.get('SHARPE_RATIO', 'N/A')}")
            print()
    else:
        print("Failed to fetch data")


def example_custom_filter():
    """Example: Custom complex filter query."""
    print_separator("Custom Query: High Performance + Low Fee Funds")

    api = PensionFundAPI()

    # Find funds with management fee <= 0.5% and 5-year yield >= 30%
    result = api.fetch_funds(
        fund_type="Pension",
        fields=[
            FundFields.FUND_ID,
            FundFields.FUND_NAME,
            FundFields.PARENT_COMPANY_NAME,
            FundFields.AVG_ANNUAL_MANAGEMENT_FEE,
            FundFields.YIELD_TRAILING_5_YRS
        ],
        complex_filters={
            "$and": [
                {FundFields.AVG_ANNUAL_MANAGEMENT_FEE: {"$lte": 0.5}},
                {FundFields.YIELD_TRAILING_5_YRS: {"$gte": 30}}
            ]
        },
        sort=f"{FundFields.YIELD_TRAILING_5_YRS} desc nulls last",
        limit=10,
        distinct=True
    )

    if result.get("success"):
        records = result.get("result", {}).get("records", [])
        if records:
            for i, fund in enumerate(records, 1):
                print(f"{i}. {fund.get('FUND_NAME', 'N/A')}")
                print(f"   Company: {fund.get('PARENT_COMPANY_NAME', 'N/A')}")
                print(f"   Management Fee: {format_percentage(fund.get('AVG_ANNUAL_MANAGEMENT_FEE'))}")
                print(f"   5-Year Yield: {format_percentage(fund.get('YIELD_TRAILING_5_YRS'))}")
                print()
        else:
            print("No funds match the criteria")
    else:
        print("Failed to fetch data")


def main():
    """Run all examples."""
    print("\n" + "#" * 60)
    print("#  Israeli Pension Fund Data API - Examples")
    print("#" * 60)

    try:
        example_top_performing_funds()
        example_low_fee_funds()
        example_risk_metrics()
        example_high_stock_exposure()
        example_age_specific_funds()
        example_insurance_funds()
        example_custom_filter()

        print("\n" + "=" * 60)
        print("  All examples completed successfully!")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"\nError running examples: {e}")
        raise


if __name__ == "__main__":
    main()
