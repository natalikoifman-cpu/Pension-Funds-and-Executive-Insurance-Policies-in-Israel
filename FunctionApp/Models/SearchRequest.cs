namespace FunctionApp.Models;

public class SearchRequest
{
    // Basic search
    public string? Query { get; set; }
    public string? FundType { get; set; }  // Pension or Executive/Insurance

    // Filter ranges
    public decimal? MinReturn { get; set; }
    public decimal? MaxReturn { get; set; }
    public decimal? MinReturn3Years { get; set; }
    public decimal? MinReturn5Years { get; set; }
    public decimal? MaxManagementFee { get; set; }
    public decimal? MaxDepositFee { get; set; }

    // Risk and exposure filters
    public string? RiskLevel { get; set; }  // Low, Medium, High
    public decimal? MaxStockExposure { get; set; }
    public decimal? MinStockExposure { get; set; }
    public decimal? MaxForeignExposure { get; set; }

    // Advanced filters
    public string? Classification { get; set; }  // Fund track/classification
    public string? ManagingCompanyId { get; set; }

    // Sorting
    public string? SortBy { get; set; }  // Field name to sort by
    public bool SortDescending { get; set; } = true;

    // Pagination
    public int PageNumber { get; set; } = 1;
    public int PageSize { get; set; } = 10;

    // Advanced API parameters
    public bool Distinct { get; set; } = false;
    public int? Months { get; set; }  // For historical data
    public string? ComplexFilters { get; set; }  // Raw JSON for complex queries
}
