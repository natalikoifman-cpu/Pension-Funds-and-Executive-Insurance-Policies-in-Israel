namespace FunctionApp.Models;

public class SearchResult
{
    public List<PensionFund> Funds { get; set; } = new();
    public int TotalCount { get; set; }
    public int PageNumber { get; set; }
    public int PageSize { get; set; }
    public int TotalPages => (int)Math.Ceiling((double)TotalCount / PageSize);
}

public class PensionFund
{
    // Basic identification
    public string Id { get; set; } = string.Empty;
    public string Name { get; set; } = string.Empty;
    public string FundType { get; set; } = string.Empty;
    public string? Classification { get; set; }

    // Company info
    public string ManagingCompany { get; set; } = string.Empty;
    public string? ManagingCompanyId { get; set; }

    // Reporting period
    public string? ReportPeriod { get; set; }

    // Fees
    public decimal ManagementFee { get; set; }
    public decimal DepositFee { get; set; }

    // Yields/Returns
    public decimal? MonthlyYield { get; set; }
    public decimal AnnualReturn { get; set; }  // Year to date yield
    public decimal? YieldTrailing3Years { get; set; }
    public decimal? YieldTrailing5Years { get; set; }
    public decimal? AvgAnnualYield3Years { get; set; }
    public decimal? AvgAnnualYield5Years { get; set; }

    // Risk metrics
    public string RiskLevel { get; set; } = string.Empty;
    public decimal? StandardDeviation { get; set; }
    public decimal? Alpha { get; set; }
    public decimal? SharpeRatio { get; set; }

    // Asset allocation / Exposure
    public decimal? TotalAssets { get; set; }
    public decimal? LiquidAssetsPercent { get; set; }
    public decimal? StockMarketExposure { get; set; }
    public decimal? ForeignExposure { get; set; }
    public decimal? ForeignCurrencyExposure { get; set; }

    // Fund flows (optional, for detailed view)
    public decimal? NetMonthlyDepositsPercent { get; set; }
    public decimal? DepositsPercent { get; set; }
    public decimal? WithdrawalsPercent { get; set; }
    public decimal? InternalTransfersPercent { get; set; }

    public DateTime LastUpdated { get; set; }
}
