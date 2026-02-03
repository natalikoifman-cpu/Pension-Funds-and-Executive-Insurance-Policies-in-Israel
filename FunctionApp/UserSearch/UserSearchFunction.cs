using System.Net;
using System.Net.Http.Headers;
using System.Text.Json;
using System.Text.Json.Serialization;
using FunctionApp.Models;
using Microsoft.Azure.Functions.Worker;
using Microsoft.Azure.Functions.Worker.Http;
using Microsoft.Extensions.Logging;

namespace FunctionApp.UserSearch;

public class UserSearchFunction
{
    private readonly ILogger<UserSearchFunction> _logger;
    private readonly HttpClient _httpClient;

    private const string ExternalApiBaseUrl = "https://fundscomparisonapi.azurewebsites.net";
    private const string ExternalApiPath = "/api/Fundsnet/898dd1cf-3a25-49fd-8fd4-6c287bb654d1/funds";

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase
    };

    private static readonly JsonSerializerOptions ApiJsonOptions = new()
    {
        PropertyNameCaseInsensitive = true
    };

    public UserSearchFunction(ILogger<UserSearchFunction> logger, IHttpClientFactory httpClientFactory)
    {
        _logger = logger;
        _httpClient = httpClientFactory.CreateClient();
    }

    [Function("Search")]
    public async Task<HttpResponseData> Run(
        [HttpTrigger(AuthorizationLevel.Anonymous, "get")] HttpRequestData req)
    {
        _logger.LogInformation("Search function processing request - calling external API");

        var query = req.Query["query"];
        var fundType = req.Query["fundType"] ?? "Pension";
        var minReturn = ParseDecimal(req.Query["minReturn"]);
        var maxManagementFee = ParseDecimal(req.Query["maxManagementFee"]);
        var pageNumber = ParseInt(req.Query["pageNumber"]) ?? 1;
        var pageSize = ParseInt(req.Query["pageSize"]) ?? 10;

        var result = await SearchFundsFromExternalApiAsync(query, fundType, minReturn, maxManagementFee, pageNumber, pageSize);

        var response = req.CreateResponse(HttpStatusCode.OK);
        response.Headers.Add("Content-Type", "application/json");
        await response.WriteStringAsync(JsonSerializer.Serialize(result, JsonOptions));
        return response;
    }

    private async Task<SearchResult> SearchFundsFromExternalApiAsync(
        string? query,
        string fundType,
        decimal? minReturn,
        decimal? maxManagementFee,
        int pageNumber,
        int pageSize)
    {
        try
        {
            var apiKey = Environment.GetEnvironmentVariable("FUNDS_API_KEY") ?? "c01221ec-b769-47a7-883c-e6cfb01276ad";

            // Map fundType to API format
            var apiFundType = fundType?.ToLower() switch
            {
                "pension" => "Pension",
                "executive" or "insurance" => "Insurance",
                _ => "Pension"
            };

            // Build query string
            var fields = "FUND_ID,FUND_NAME,FUND_TYPE,PARENT_COMPANY_NAME,AVG_ANNUAL_MANAGEMENT_FEE,AVG_DEPOSIT_FEE,YEAR_TO_DATE_YIELD,STOCK_MARKET_EXPOSURE";
            var offset = (pageNumber - 1) * pageSize;

            var queryParams = new List<string>
            {
                $"fields={fields}",
                $"limit={pageSize}",
                $"offset={offset}"
            };

            // Add search query if provided
            if (!string.IsNullOrEmpty(query))
            {
                queryParams.Add($"q={Uri.EscapeDataString(query)}");
            }

            // Build complex filters for minReturn and maxManagementFee
            var filters = new List<string>();
            if (minReturn.HasValue)
            {
                filters.Add($"{{\"YEAR_TO_DATE_YIELD\":{{\"$gte\":{minReturn.Value}}}}}");
            }
            if (maxManagementFee.HasValue)
            {
                filters.Add($"{{\"AVG_ANNUAL_MANAGEMENT_FEE\":{{\"$lte\":{maxManagementFee.Value}}}}}");
            }

            if (filters.Count > 0)
            {
                var complexFilter = filters.Count == 1
                    ? filters[0]
                    : $"{{\"$and\":[{string.Join(",", filters)}]}}";
                queryParams.Add($"complexFilters={Uri.EscapeDataString(complexFilter)}");
            }

            var url = $"{ExternalApiBaseUrl}{ExternalApiPath}/{apiFundType}?{string.Join("&", queryParams)}";

            _logger.LogInformation("Calling external API: {Url}", url);

            var request = new HttpRequestMessage(HttpMethod.Get, url);
            request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", apiKey);

            var apiResponse = await _httpClient.SendAsync(request);
            var content = await apiResponse.Content.ReadAsStringAsync();

            if (!apiResponse.IsSuccessStatusCode)
            {
                _logger.LogError("External API error: {StatusCode} - {Content}", apiResponse.StatusCode, content);
                return new SearchResult { Funds = new List<PensionFund>(), TotalCount = 0, PageNumber = pageNumber, PageSize = pageSize };
            }

            var apiResult = JsonSerializer.Deserialize<ExternalApiResponse>(content, ApiJsonOptions);

            if (apiResult?.Success != true || apiResult.Result?.Records == null)
            {
                _logger.LogWarning("External API returned unsuccessful or no records");
                return new SearchResult { Funds = new List<PensionFund>(), TotalCount = 0, PageNumber = pageNumber, PageSize = pageSize };
            }

            var funds = apiResult.Result.Records.Select(MapToFund).ToList();
            var totalCount = apiResult.Result.Total;

            return new SearchResult
            {
                Funds = funds,
                TotalCount = totalCount,
                PageNumber = pageNumber,
                PageSize = pageSize
            };
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error calling external API");
            return new SearchResult { Funds = new List<PensionFund>(), TotalCount = 0, PageNumber = pageNumber, PageSize = pageSize };
        }
    }

    private static PensionFund MapToFund(ExternalFundRecord record)
    {
        // Determine risk level based on stock market exposure
        var riskLevel = record.StockMarketExposure switch
        {
            >= 70 => "High",
            >= 30 => "Medium",
            _ => "Low"
        };

        // Map "Insurance" to "Executive" for frontend compatibility
        var fundType = record.FundType?.ToLower() == "insurance" ? "Executive" : (record.FundType ?? "Pension");

        return new PensionFund
        {
            Id = record.FundId ?? "",
            Name = record.FundName ?? "",
            FundType = fundType,
            ManagingCompany = record.ParentCompanyName ?? "",
            AnnualReturn = record.YearToDateYield ?? 0,
            ManagementFee = record.AvgAnnualManagementFee ?? 0,
            DepositFee = record.AvgDepositFee ?? 0,
            RiskLevel = riskLevel,
            LastUpdated = DateTime.UtcNow
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

// Models for external API response
public class ExternalApiResponse
{
    public bool Success { get; set; }
    public ExternalApiResult? Result { get; set; }
}

public class ExternalApiResult
{
    public int Total { get; set; }
    public int Limit { get; set; }
    public List<ExternalFundRecord>? Records { get; set; }
}

public class ExternalFundRecord
{
    [JsonPropertyName("FUND_ID")]
    public string? FundId { get; set; }

    [JsonPropertyName("FUND_NAME")]
    public string? FundName { get; set; }

    [JsonPropertyName("FUND_TYPE")]
    public string? FundType { get; set; }

    [JsonPropertyName("PARENT_COMPANY_NAME")]
    public string? ParentCompanyName { get; set; }

    [JsonPropertyName("AVG_ANNUAL_MANAGEMENT_FEE")]
    public decimal? AvgAnnualManagementFee { get; set; }

    [JsonPropertyName("AVG_DEPOSIT_FEE")]
    public decimal? AvgDepositFee { get; set; }

    [JsonPropertyName("YEAR_TO_DATE_YIELD")]
    public decimal? YearToDateYield { get; set; }

    [JsonPropertyName("STOCK_MARKET_EXPOSURE")]
    public decimal? StockMarketExposure { get; set; }
}
