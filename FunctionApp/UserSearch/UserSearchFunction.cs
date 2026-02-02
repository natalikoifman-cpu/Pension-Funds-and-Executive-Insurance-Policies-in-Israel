using System.Net;
using System.Text.Json;
using FunctionApp.Models;
using Microsoft.Azure.Functions.Worker;
using Microsoft.Azure.Functions.Worker.Http;
using Microsoft.Extensions.Logging;

namespace FunctionApp.UserSearch;

public class UserSearchFunction
{
    private readonly ILogger<UserSearchFunction> _logger;
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase
    };

    public UserSearchFunction(ILogger<UserSearchFunction> logger)
    {
        _logger = logger;
    }

    [Function("Search")]
    public async Task<HttpResponseData> Run(
        [HttpTrigger(AuthorizationLevel.Anonymous, "get")] HttpRequestData req)
    {
        _logger.LogInformation("Search function processing request");

        var query = req.Query["query"];
        var fundType = req.Query["fundType"];
        var minReturn = ParseDecimal(req.Query["minReturn"]);
        var maxManagementFee = ParseDecimal(req.Query["maxManagementFee"]);
        var riskLevel = req.Query["riskLevel"];
        var pageNumber = ParseInt(req.Query["pageNumber"]) ?? 1;
        var pageSize = ParseInt(req.Query["pageSize"]) ?? 10;

        var searchRequest = new SearchRequest
        {
            Query = query,
            FundType = fundType,
            MinReturn = minReturn,
            MaxManagementFee = maxManagementFee,
            RiskLevel = riskLevel,
            PageNumber = pageNumber,
            PageSize = pageSize
        };

        var result = await SearchFundsAsync(searchRequest);

        var response = req.CreateResponse(HttpStatusCode.OK);
        response.Headers.Add("Content-Type", "application/json");
        await response.WriteStringAsync(JsonSerializer.Serialize(result, JsonOptions));
        return response;
    }

    private async Task<SearchResult> SearchFundsAsync(SearchRequest request)
    {
        // Sample data - in production, this would query a database or external API
        var allFunds = GetSampleFunds();

        var filteredFunds = allFunds.AsQueryable();

        if (!string.IsNullOrEmpty(request.Query))
        {
            var queryLower = request.Query.ToLower();
            filteredFunds = filteredFunds.Where(f =>
                f.Name.ToLower().Contains(queryLower) ||
                f.ManagingCompany.ToLower().Contains(queryLower));
        }

        if (!string.IsNullOrEmpty(request.FundType))
        {
            filteredFunds = filteredFunds.Where(f =>
                f.FundType.Equals(request.FundType, StringComparison.OrdinalIgnoreCase));
        }

        if (request.MinReturn.HasValue)
        {
            filteredFunds = filteredFunds.Where(f => f.AnnualReturn >= request.MinReturn.Value);
        }

        if (request.MaxManagementFee.HasValue)
        {
            filteredFunds = filteredFunds.Where(f => f.ManagementFee <= request.MaxManagementFee.Value);
        }

        if (!string.IsNullOrEmpty(request.RiskLevel))
        {
            filteredFunds = filteredFunds.Where(f =>
                f.RiskLevel.Equals(request.RiskLevel, StringComparison.OrdinalIgnoreCase));
        }

        var totalCount = filteredFunds.Count();
        var pagedFunds = filteredFunds
            .Skip((request.PageNumber - 1) * request.PageSize)
            .Take(request.PageSize)
            .ToList();

        return await Task.FromResult(new SearchResult
        {
            Funds = pagedFunds,
            TotalCount = totalCount,
            PageNumber = request.PageNumber,
            PageSize = request.PageSize
        });
    }

    private List<PensionFund> GetSampleFunds()
    {
        return new List<PensionFund>
        {
            new()
            {
                Id = "1",
                Name = "מיטב דש גמל",
                FundType = "Pension",
                ManagingCompany = "מיטב דש",
                AnnualReturn = 8.5m,
                ManagementFee = 0.5m,
                DepositFee = 0.25m,
                RiskLevel = "Medium",
                LastUpdated = DateTime.UtcNow
            },
            new()
            {
                Id = "2",
                Name = "הראל פנסיה",
                FundType = "Pension",
                ManagingCompany = "הראל",
                AnnualReturn = 7.8m,
                ManagementFee = 0.45m,
                DepositFee = 0.2m,
                RiskLevel = "Low",
                LastUpdated = DateTime.UtcNow
            },
            new()
            {
                Id = "3",
                Name = "מנורה מבטחים פנסיה",
                FundType = "Pension",
                ManagingCompany = "מנורה מבטחים",
                AnnualReturn = 9.2m,
                ManagementFee = 0.55m,
                DepositFee = 0.3m,
                RiskLevel = "High",
                LastUpdated = DateTime.UtcNow
            },
            new()
            {
                Id = "4",
                Name = "כלל ביטוח מנהלים",
                FundType = "Executive",
                ManagingCompany = "כלל ביטוח",
                AnnualReturn = 6.5m,
                ManagementFee = 0.6m,
                DepositFee = 0.35m,
                RiskLevel = "Low",
                LastUpdated = DateTime.UtcNow
            },
            new()
            {
                Id = "5",
                Name = "פניקס ביטוח מנהלים",
                FundType = "Executive",
                ManagingCompany = "הפניקס",
                AnnualReturn = 7.2m,
                ManagementFee = 0.52m,
                DepositFee = 0.28m,
                RiskLevel = "Medium",
                LastUpdated = DateTime.UtcNow
            }
        };
    }

    private static decimal? ParseDecimal(string? value)
    {
        if (string.IsNullOrEmpty(value)) return null;
        return decimal.TryParse(value, out var result) ? result : null;
    }

    private static int? ParseInt(string? value)
    {
        if (string.IsNullOrEmpty(value)) return null;
        return int.TryParse(value, out var result) ? result : null;
    }
}
