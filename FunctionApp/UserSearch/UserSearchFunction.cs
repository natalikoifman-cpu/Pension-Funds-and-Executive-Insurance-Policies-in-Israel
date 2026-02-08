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

    // All available fields from the API
    private const string AllFields = "FUND_ID,FUND_NAME,FUND_CLASSIFICATION,PARENT_COMPANY_NAME,PARENT_COMPANY_ID," +
        "REPORT_PERIOD,TOTAL_ASSETS,AVG_ANNUAL_MANAGEMENT_FEE,AVG_DEPOSIT_FEE," +
        "MONTHLY_YIELD,YEAR_TO_DATE_YIELD,YIELD_TRAILING_3_YRS,YIELD_TRAILING_5_YRS," +
        "AVG_ANNUAL_YIELD_TRAILING_3YRS,AVG_ANNUAL_YIELD_TRAILING_5YRS," +
        "STANDARD_DEVIATION,ALPHA,SHARPE_RATIO," +
        "LIQUID_ASSETS_PERCENT,STOCK_MARKET_EXPOSURE,FOREIGN_EXPOSURE,FOREIGN_CURRENCY_EXPOSURE";

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
        [HttpTrigger(AuthorizationLevel.Anonymous, "get", "options")] HttpRequestData req)
    {
        _logger.LogInformation("Search function processing request - calling external API");

        // Parse all query parameters
        var query = req.Query["query"];
        var fundType = req.Query["fundType"] ?? "Pension";
        var minReturn = ParseDecimal(req.Query["minReturn"]);
        var maxManagementFee = ParseDecimal(req.Query["maxManagementFee"]);
        var minReturn3Years = ParseDecimal(req.Query["minReturn3Years"]);
        var minReturn5Years = ParseDecimal(req.Query["minReturn5Years"]);
        var maxStockExposure = ParseDecimal(req.Query["maxStockExposure"]);
        var minStockExposure = ParseDecimal(req.Query["minStockExposure"]);
        var classification = req.Query["classification"];
        var sortBy = req.Query["sortBy"] ?? "YEAR_TO_DATE_YIELD";
        var sortDesc = req.Query["sortDesc"] != "false";
        var pageNumber = ParseInt(req.Query["pageNumber"]) ?? 1;
        var pageSize = ParseInt(req.Query["pageSize"]) ?? 10;
        var distinct = req.Query["distinct"] == "true";
        var complexFilters = req.Query["complexFilters"];

        var result = await SearchFundsFromExternalApiAsync(
            query, fundType, minReturn, maxManagementFee,
            minReturn3Years, minReturn5Years, maxStockExposure, minStockExposure,
            classification, sortBy, sortDesc, pageNumber, pageSize, distinct, complexFilters);

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
        decimal? minReturn3Years,
        decimal? minReturn5Years,
        decimal? maxStockExposure,
        decimal? minStockExposure,
        string? classification,
        string sortBy,
        bool sortDesc,
        int pageNumber,
        int pageSize,
        bool distinct,
        string? complexFilters)
    {
        try
        {
            var apiKey = Environment.GetEnvironmentVariable("FUNDS_API_KEY") ?? "c01221ec-b769-47a7-883c-e6cfb01276ad";

            // Map fundType to API format
            // New fund types (gemel, hishtalmut, gemel-child) use the Pension endpoint
            // with FUND_CLASSIFICATION complex filter
            var apiFundType = fundType?.ToLower() switch
            {
                "pension" => "Pension",
                "executive" or "insurance" => "Insurance",
                "gemel" or "hishtalmut" or "gemel-child" => "Pension",
                _ => "Pension"
            };

            // Auto-inject FUND_CLASSIFICATION filter for new fund types
            var fundClassificationFilter = fundType?.ToLower() switch
            {
                "gemel" => "{\"FUND_CLASSIFICATION\":{\"$eq\":\"קופת גמל להשקעה\"}}",
                "hishtalmut" => "{\"FUND_CLASSIFICATION\":{\"$eq\":\"קרנות השתלמות\"}}",
                "gemel-child" => "{\"FUND_CLASSIFICATION\":{\"$eq\":\"קופת גמל להשקעה - חסכון לילד\"}}",
                _ => null
            };

            if (!string.IsNullOrEmpty(fundClassificationFilter))
            {
                complexFilters = string.IsNullOrEmpty(complexFilters)
                    ? fundClassificationFilter
                    : $"{{\"$and\":[{fundClassificationFilter},{complexFilters}]}}";
            }

            var offset = (pageNumber - 1) * pageSize;

            var queryParams = new List<string>
            {
                $"fields={AllFields}",
                $"limit={pageSize}",
                $"offset={offset}"
            };

            // Add search query if provided
            if (!string.IsNullOrEmpty(query))
            {
                queryParams.Add($"q={Uri.EscapeDataString(query)}");
            }

            // Build sort parameter
            var sortField = MapSortField(sortBy);
            var sortDirection = sortDesc ? "desc" : "asc";
            queryParams.Add($"sort={Uri.EscapeDataString($"{sortField} {sortDirection} nulls last")}");

            // Add distinct if requested (requires sort)
            if (distinct)
            {
                queryParams.Add("distinct=true");
            }

            // Build complex filters
            var filters = BuildComplexFilters(minReturn, maxManagementFee, minReturn3Years, minReturn5Years,
                maxStockExposure, minStockExposure, classification, complexFilters);

            if (!string.IsNullOrEmpty(filters))
            {
                queryParams.Add($"complexFilters={Uri.EscapeDataString(filters)}");
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

            // Preserve the original fund type for display purposes
            var mappedFundType = fundType?.ToLower() switch
            {
                "executive" or "insurance" => "Executive",
                "gemel" => "Gemel",
                "hishtalmut" => "Hishtalmut",
                "gemel-child" => "GemelChild",
                _ => "Pension"
            };
            var funds = apiResult.Result.Records.Select(r => MapToFund(r, mappedFundType)).ToList();
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

    private static string MapSortField(string sortBy)
    {
        return sortBy?.ToUpper() switch
        {
            "ANNUAL_RETURN" or "ANNUALRETURN" or "YEAR_TO_DATE_YIELD" => "YEAR_TO_DATE_YIELD",
            "RETURN_3_YEARS" or "RETURN3YEARS" or "YIELD_TRAILING_3_YRS" => "YIELD_TRAILING_3_YRS",
            "RETURN_5_YEARS" or "RETURN5YEARS" or "YIELD_TRAILING_5_YRS" => "YIELD_TRAILING_5_YRS",
            "AVG_ANNUAL_YIELD_TRAILING_3YRS" => "AVG_ANNUAL_YIELD_TRAILING_3YRS",
            "AVG_ANNUAL_YIELD_TRAILING_5YRS" => "AVG_ANNUAL_YIELD_TRAILING_5YRS",
            "MANAGEMENT_FEE" or "MANAGEMENTFEE" or "AVG_ANNUAL_MANAGEMENT_FEE" => "AVG_ANNUAL_MANAGEMENT_FEE",
            "DEPOSIT_FEE" or "DEPOSITFEE" or "AVG_DEPOSIT_FEE" => "AVG_DEPOSIT_FEE",
            "SHARPE" or "SHARPE_RATIO" => "SHARPE_RATIO",
            "ALPHA" => "ALPHA",
            "STANDARD_DEVIATION" => "STANDARD_DEVIATION",
            "STOCK_EXPOSURE" or "STOCK_MARKET_EXPOSURE" => "STOCK_MARKET_EXPOSURE",
            "TOTAL_ASSETS" => "TOTAL_ASSETS",
            _ => "YEAR_TO_DATE_YIELD"
        };
    }

    private static string? BuildComplexFilters(
        decimal? minReturn,
        decimal? maxManagementFee,
        decimal? minReturn3Years,
        decimal? minReturn5Years,
        decimal? maxStockExposure,
        decimal? minStockExposure,
        string? classification,
        string? existingFilters)
    {
        var conditions = new List<string>();

        if (minReturn.HasValue)
        {
            conditions.Add($"{{\"YEAR_TO_DATE_YIELD\":{{\"$gte\":{minReturn.Value}}}}}");
        }

        if (maxManagementFee.HasValue)
        {
            conditions.Add($"{{\"AVG_ANNUAL_MANAGEMENT_FEE\":{{\"$lte\":{maxManagementFee.Value}}}}}");
        }

        if (minReturn3Years.HasValue)
        {
            conditions.Add($"{{\"YIELD_TRAILING_3_YRS\":{{\"$gte\":{minReturn3Years.Value}}}}}");
        }

        if (minReturn5Years.HasValue)
        {
            conditions.Add($"{{\"YIELD_TRAILING_5_YRS\":{{\"$gte\":{minReturn5Years.Value}}}}}");
        }

        if (maxStockExposure.HasValue)
        {
            conditions.Add($"{{\"STOCK_MARKET_EXPOSURE_PERCENT\":{{\"$lte\":{maxStockExposure.Value}}}}}");
        }

        if (minStockExposure.HasValue)
        {
            conditions.Add($"{{\"STOCK_MARKET_EXPOSURE_PERCENT\":{{\"$gte\":{minStockExposure.Value}}}}}");
        }

        if (!string.IsNullOrEmpty(classification))
        {
            conditions.Add($"{{\"FUND_CLASSIFICATION\":{{\"$eq\":\"{classification}\"}}}}");
        }

        // Add existing complex filters if provided
        if (!string.IsNullOrEmpty(existingFilters))
        {
            conditions.Add(existingFilters);
        }

        if (conditions.Count == 0)
        {
            return null;
        }

        if (conditions.Count == 1)
        {
            return conditions[0];
        }

        return $"{{\"$and\":[{string.Join(",", conditions)}]}}";
    }

    private static PensionFund MapToFund(ExternalFundRecord record, string fundType)
    {
        // Determine risk level based on stock market exposure
        var riskLevel = record.StockMarketExposure switch
        {
            >= 70 => "High",
            >= 30 => "Medium",
            _ => "Low"
        };

        return new PensionFund
        {
            Id = record.FundId ?? "",
            Name = record.FundName ?? "",
            FundType = fundType,
            Classification = record.FundClassification,
            ManagingCompany = record.ParentCompanyName ?? "",
            ManagingCompanyId = record.ParentCompanyId,
            ReportPeriod = record.ReportPeriod,
            ManagementFee = record.AvgAnnualManagementFee ?? 0,
            DepositFee = record.AvgDepositFee ?? 0,
            MonthlyYield = record.MonthlyYield,
            AnnualReturn = record.YearToDateYield ?? 0,
            YieldTrailing3Years = record.YieldTrailing3Yrs,
            YieldTrailing5Years = record.YieldTrailing5Yrs,
            AvgAnnualYield3Years = record.AvgAnnualYieldTrailing3Yrs,
            AvgAnnualYield5Years = record.AvgAnnualYieldTrailing5Yrs,
            StandardDeviation = record.StandardDeviation,
            Alpha = record.Alpha,
            SharpeRatio = record.SharpeRatio,
            TotalAssets = record.TotalAssets,
            LiquidAssetsPercent = record.LiquidAssetsPercent,
            StockMarketExposure = record.StockMarketExposure,
            ForeignExposure = record.ForeignExposure,
            ForeignCurrencyExposure = record.ForeignCurrencyExposure,
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

    [JsonPropertyName("FUND_CLASSIFICATION")]
    public string? FundClassification { get; set; }

    [JsonPropertyName("PARENT_COMPANY_NAME")]
    public string? ParentCompanyName { get; set; }

    [JsonPropertyName("PARENT_COMPANY_ID")]
    public string? ParentCompanyId { get; set; }

    [JsonPropertyName("REPORT_PERIOD")]
    public string? ReportPeriod { get; set; }

    [JsonPropertyName("TOTAL_ASSETS")]
    public decimal? TotalAssets { get; set; }

    [JsonPropertyName("AVG_ANNUAL_MANAGEMENT_FEE")]
    public decimal? AvgAnnualManagementFee { get; set; }

    [JsonPropertyName("AVG_DEPOSIT_FEE")]
    public decimal? AvgDepositFee { get; set; }

    [JsonPropertyName("MONTHLY_YIELD")]
    public decimal? MonthlyYield { get; set; }

    [JsonPropertyName("YEAR_TO_DATE_YIELD")]
    public decimal? YearToDateYield { get; set; }

    [JsonPropertyName("YIELD_TRAILING_3_YRS")]
    public decimal? YieldTrailing3Yrs { get; set; }

    [JsonPropertyName("YIELD_TRAILING_5_YRS")]
    public decimal? YieldTrailing5Yrs { get; set; }

    [JsonPropertyName("AVG_ANNUAL_YIELD_TRAILING_3YRS")]
    public decimal? AvgAnnualYieldTrailing3Yrs { get; set; }

    [JsonPropertyName("AVG_ANNUAL_YIELD_TRAILING_5YRS")]
    public decimal? AvgAnnualYieldTrailing5Yrs { get; set; }

    [JsonPropertyName("STANDARD_DEVIATION")]
    public decimal? StandardDeviation { get; set; }

    [JsonPropertyName("ALPHA")]
    public decimal? Alpha { get; set; }

    [JsonPropertyName("SHARPE_RATIO")]
    public decimal? SharpeRatio { get; set; }

    [JsonPropertyName("LIQUID_ASSETS_PERCENT")]
    public decimal? LiquidAssetsPercent { get; set; }

    [JsonPropertyName("STOCK_MARKET_EXPOSURE")]
    public decimal? StockMarketExposure { get; set; }

    [JsonPropertyName("FOREIGN_EXPOSURE")]
    public decimal? ForeignExposure { get; set; }

    [JsonPropertyName("FOREIGN_CURRENCY_EXPOSURE")]
    public decimal? ForeignCurrencyExposure { get; set; }
}
