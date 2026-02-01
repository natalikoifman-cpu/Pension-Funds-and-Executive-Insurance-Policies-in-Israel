namespace FunctionApp.Models;

public class SearchRequest
{
    public string? Query { get; set; }
    public string? FundType { get; set; }
    public decimal? MinReturn { get; set; }
    public decimal? MaxManagementFee { get; set; }
    public string? RiskLevel { get; set; }
    public int PageNumber { get; set; } = 1;
    public int PageSize { get; set; } = 10;
}
