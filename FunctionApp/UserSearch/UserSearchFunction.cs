using System.Net;
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

    // data.gov.il CKAN API (Israel government open data portal)
    private const string DataGovApiUrl = "https://data.gov.il/api/3/action/datastore_search";

    // Resource IDs for each fund type (2024-present daily data)
    private static readonly Dictionary<string, string> ResourceIds = new()
    {
        ["Pension"] = "6d47d6b5-cb08-488b-b333-f1e717b1e1bd",
        ["Insurance"] = "c6c62cc7-fe02-4b18-8f3e-813abfbb4647",
        ["Provident"] = "a30dcbea-a1d2-482c-ae29-8f781f5025fb"
    };

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
        _logger.LogInformation("Search function processing request via data.gov.il CKAN API");

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

        var result = await SearchFundsAsync(
            query, fundType, minReturn, maxManagementFee,
            minReturn3Years, minReturn5Years, maxStockExposure, minStockExposure,
            classification, sortBy, sortDesc, pageNumber, pageSize, distinct);

        var response = req.CreateResponse(HttpStatusCode.OK);
        response.Headers.Add("Content-Type", "application/json");
        await response.WriteStringAsync(JsonSerializer.Serialize(result, JsonOptions));
        return response;
    }

    private async Task<SearchResult> SearchFundsAsync(
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
        bool distinct)
    {
        try
        {
            // Map fundType to data.gov.il resource
            var resourceKey = fundType?.ToLower() switch
            {
                "pension" => "Pension",
                "executive" or "insurance" => "Insurance",
                "gemel" or "hishtalmut" or "gemelchild" or "gemel-child" => "Provident",
                _ => "Pension"
            };

            if (!ResourceIds.TryGetValue(resourceKey, out var resourceId))
            {
                resourceId = ResourceIds["Pension"];
            }

            // Build CKAN filters (exact match only)
            var filters = new Dictionary<string, string>();

            // Auto-inject FUND_CLASSIFICATION filter for specific fund types
            var fundClassification = fundType?.ToLower() switch
            {
                "gemel" => "קופת גמל להשקעה",
                "hishtalmut" => "קרנות השתלמות",
                "gemelchild" or "gemel-child" => "קופת גמל להשקעה - חסכון לילד",
                _ => null
            };

            if (!string.IsNullOrEmpty(fundClassification))
                filters["FUND_CLASSIFICATION"] = fundClassification;

            if (!string.IsNullOrEmpty(classification) && !filters.ContainsKey("FUND_CLASSIFICATION"))
                filters["FUND_CLASSIFICATION"] = classification;

            // Check if we need range filtering (CKAN doesn't support range queries)
            bool hasRangeFilters = minReturn.HasValue || maxManagementFee.HasValue ||
                minReturn3Years.HasValue || minReturn5Years.HasValue ||
                maxStockExposure.HasValue || minStockExposure.HasValue;

            // When range filters are present, fetch a larger set and filter in-memory
            var fetchLimit = hasRangeFilters ? Math.Max(pageSize * 10, 200) : pageSize;
            var fetchOffset = hasRangeFilters ? 0 : (pageNumber - 1) * pageSize;

            // Build sort parameter
            var sortField = MapSortField(sortBy);
            var sortDirection = sortDesc ? "desc" : "asc";
            var sort = $"{sortField} {sortDirection}";

            // Build CKAN query URL
            var queryParams = new List<string>
            {
                $"resource_id={resourceId}",
                $"limit={fetchLimit}",
                $"offset={fetchOffset}",
                $"sort={Uri.EscapeDataString(sort)}",
                "include_total=true"
            };

            if (!string.IsNullOrEmpty(query))
            {
                queryParams.Add($"q={Uri.EscapeDataString(query)}");
            }

            if (filters.Count > 0)
            {
                var filtersJson = JsonSerializer.Serialize(filters);
                queryParams.Add($"filters={Uri.EscapeDataString(filtersJson)}");
            }

            if (distinct)
            {
                queryParams.Add("distinct=true");
            }

            var url = $"{DataGovApiUrl}?{string.Join("&", queryParams)}";

            _logger.LogInformation("Calling data.gov.il CKAN API: {Url}", url);

            var apiResponse = await _httpClient.GetAsync(url);
            var content = await apiResponse.Content.ReadAsStringAsync();

            if (!apiResponse.IsSuccessStatusCode)
            {
                _logger.LogError("data.gov.il API error: {StatusCode} - {Content}", apiResponse.StatusCode, content);
                return new SearchResult { Funds = new List<PensionFund>(), TotalCount = 0, PageNumber = pageNumber, PageSize = pageSize };
            }

            var apiResult = JsonSerializer.Deserialize<CkanApiResponse>(content, ApiJsonOptions);

            if (apiResult?.Success != true || apiResult.Result?.Records == null)
            {
                _logger.LogWarning("data.gov.il API returned unsuccessful or no records");
                return new SearchResult { Funds = new List<PensionFund>(), TotalCount = 0, PageNumber = pageNumber, PageSize = pageSize };
            }

            // Map to fund records
            var mappedFundType = fundType?.ToLower() switch
            {
                "executive" or "insurance" => "Executive",
                "gemel" => "Gemel",
                "hishtalmut" => "Hishtalmut",
                "gemelchild" or "gemel-child" => "GemelChild",
                _ => "Pension"
            };

            var records = apiResult.Result.Records;
            var totalCount = apiResult.Result.Total;

            // Apply range filters in-memory (CKAN only supports exact match)
            if (hasRangeFilters)
            {
                records = records.Where(r =>
                    (!minReturn.HasValue || r.YearToDateYield >= minReturn.Value) &&
                    (!maxManagementFee.HasValue || r.AvgAnnualManagementFee <= maxManagementFee.Value) &&
                    (!minReturn3Years.HasValue || r.YieldTrailing3Yrs >= minReturn3Years.Value) &&
                    (!minReturn5Years.HasValue || r.YieldTrailing5Yrs >= minReturn5Years.Value) &&
                    (!maxStockExposure.HasValue || r.StockMarketExposure <= maxStockExposure.Value) &&
                    (!minStockExposure.HasValue || r.StockMarketExposure >= minStockExposure.Value)
                ).ToList();

                totalCount = records.Count;

                // Apply pagination on filtered results
                var offset = (pageNumber - 1) * pageSize;
                records = records.Skip(offset).Take(pageSize).ToList();
            }

            var funds = records.Select(r => MapToFund(r, mappedFundType)).ToList();

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
            _logger.LogError(ex, "Error calling data.gov.il API");
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

    private static PensionFund MapToFund(CkanFundRecord record, string fundType)
    {
        // Determine risk level based on stock market exposure
        var riskLevel = record.StockMarketExposure switch
        {
            >= 70 => "High",
            >= 30 => "Medium",
            _ => "Low"
        };

        // Provident/Gemel datasets use MANAGING_CORPORATION instead of PARENT_COMPANY_NAME
        var companyName = record.ParentCompanyName ?? record.ManagingCorporation ?? record.ControllingCorporation ?? "";

        return new PensionFund
        {
            Id = record.FundId?.ToString() ?? "",
            Name = record.FundName ?? "",
            FundType = fundType,
            Classification = record.FundClassification,
            ManagingCompany = companyName,
            ManagingCompanyId = record.ParentCompanyId?.ToString(),
            ReportPeriod = record.ReportPeriod?.ToString(),
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

// Models for data.gov.il CKAN API response
public class CkanApiResponse
{
    public bool Success { get; set; }
    public CkanApiResult? Result { get; set; }
}

public class CkanApiResult
{
    public int Total { get; set; }
    public int Limit { get; set; }
    public List<CkanFundRecord>? Records { get; set; }
}

public class CkanFundRecord
{
    [JsonPropertyName("FUND_ID")]
    public long? FundId { get; set; }

    [JsonPropertyName("FUND_NAME")]
    public string? FundName { get; set; }

    [JsonPropertyName("FUND_CLASSIFICATION")]
    public string? FundClassification { get; set; }

    // Pension & Insurance datasets
    [JsonPropertyName("PARENT_COMPANY_NAME")]
    public string? ParentCompanyName { get; set; }

    [JsonPropertyName("PARENT_COMPANY_ID")]
    public long? ParentCompanyId { get; set; }

    // Provident/Gemel dataset (different field names)
    [JsonPropertyName("MANAGING_CORPORATION")]
    public string? ManagingCorporation { get; set; }

    [JsonPropertyName("CONTROLLING_CORPORATION")]
    public string? ControllingCorporation { get; set; }

    [JsonPropertyName("REPORT_PERIOD")]
    public long? ReportPeriod { get; set; }

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
