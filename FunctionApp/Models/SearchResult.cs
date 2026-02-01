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
    public string Id { get; set; } = string.Empty;
    public string Name { get; set; } = string.Empty;
    public string FundType { get; set; } = string.Empty;
    public string ManagingCompany { get; set; } = string.Empty;
    public decimal AnnualReturn { get; set; }
    public decimal ManagementFee { get; set; }
    public decimal DepositFee { get; set; }
    public string RiskLevel { get; set; } = string.Empty;
    public DateTime LastUpdated { get; set; }
}
