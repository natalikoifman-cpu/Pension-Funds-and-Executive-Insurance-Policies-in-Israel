using System.Net;
using System.Net.Http.Headers;
using System.Text.Json;
using System.Text.Json.Serialization;
using FunctionApp.Models;
using FunctionApp.Services;
using FunctionApp.UserSearch;
using Microsoft.Azure.Functions.Worker;
using Microsoft.Azure.Functions.Worker.Http;
using Microsoft.Extensions.Logging;

namespace FunctionApp.Chat;

public class ChatFunction
{
    private readonly ILogger<ChatFunction> _logger;
    private readonly IAzureOpenAIService _openAIService;
    private readonly HttpClient _httpClient;

    private const string ExternalApiBaseUrl = "https://fundscomparisonapi.azurewebsites.net";
    private const string ExternalApiPath = "/api/Fundsnet/898dd1cf-3a25-49fd-8fd4-6c287bb654d1/funds";

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

    private const string SystemPrompt = @"אתה כלי להצגת נתונים על מוצרים פיננסיים בישראל. הנתונים מגיעים מאתר משרד האוצר.

מוצרים נתמכים:
- קרנות פנסיה
- ביטוחי מנהלים
- קופות גמל להשקעה
- קרנות השתלמות
- קופות גמל לחסכון לילד

כללים:
1. ענה תמיד בעברית אלא אם המשתמש פונה באנגלית
2. הצג נתונים בלבד - אין לספק ייעוץ פנסיוני או המלצות אישיות
3. אין להמליץ על קרן ספציפית או לומר איזו קרן ""הכי טובה"" למשתמש
4. הסבר מושגים פיננסיים בצורה פשוטה ועובדתית
5. אם המשתמש מבקש המלצה, הפנה אותו לבעל רישיון ייעוץ פנסיוני מטעם משרד האוצר

אתה יכול:
- להציג נתונים מאתר משרד האוצר
- להשוות בין קרנות/קופות על בסיס נתונים פומביים
- להציג תשואות, דמי ניהול וסטטיסטיקות
- להשוות בין קופות גמל, קרנות השתלמות וקופות חסכון לילד

אתה לא יכול:
- להמליץ על קרן או קופה ספציפית
- לספק ייעוץ מותאם אישית
- להציע איזו קרן ""הכי מתאימה"" למשתמש
- לתת המלצות השקעה

סיים כל תשובה עם ההודעה הבאה:
---
אתר זה אינו מספק ייעוץ פנסיוני. האתר מציג נתונים מאתר משרד האוצר בלבד. לקבלת ייעוץ פנסיוני יש לפנות לבעל רישיון מטעם משרד האוצר.

נתונים זמינים:
- תשואות (חודשית, שנתית, 3 שנים, 5 שנים)
- דמי ניהול ודמי הפקדה
- מדדי סיכון (סטיית תקן, שארפ, אלפא)
- חשיפה למניות, לחו""ל ולמט""ח
- סך נכסים מנוהלים";

    public ChatFunction(ILogger<ChatFunction> logger, IAzureOpenAIService openAIService, IHttpClientFactory httpClientFactory)
    {
        _logger = logger;
        _openAIService = openAIService;
        _httpClient = httpClientFactory.CreateClient();
    }

    [Function("Chat")]
    public async Task<HttpResponseData> Run(
        [HttpTrigger(AuthorizationLevel.Anonymous, "post", "options")] HttpRequestData req)
    {
        _logger.LogInformation("Chat function processing request");

        ChatRequest? chatRequest;
        try
        {
            var requestBody = await new StreamReader(req.Body).ReadToEndAsync();
            chatRequest = JsonSerializer.Deserialize<ChatRequest>(requestBody, new JsonSerializerOptions
            {
                PropertyNameCaseInsensitive = true
            });
        }
        catch (JsonException ex)
        {
            _logger.LogError(ex, "Failed to parse chat request");
            var badRequest = req.CreateResponse(HttpStatusCode.BadRequest);
            await badRequest.WriteAsJsonAsync(new { error = "Invalid request format" });
            return badRequest;
        }

        if (chatRequest == null || string.IsNullOrEmpty(chatRequest.Message))
        {
            var badRequest = req.CreateResponse(HttpStatusCode.BadRequest);
            await badRequest.WriteAsJsonAsync(new { error = "Message is required" });
            return badRequest;
        }

        var chatResponse = await ProcessChatAsync(chatRequest);

        var response = req.CreateResponse(HttpStatusCode.OK);
        response.Headers.Add("Content-Type", "application/json");
        await response.WriteStringAsync(JsonSerializer.Serialize(chatResponse, JsonOptions));
        return response;
    }

    private async Task<ChatResponse> ProcessChatAsync(ChatRequest request)
    {
        var sessionId = request.SessionId ?? Guid.NewGuid().ToString();
        var intent = AnalyzeIntent(request.Message);
        var suggestedFunds = await GetRelevantFundsAsync(intent);
        var suggestedQuestions = GetSuggestedQuestions(intent);

        string responseMessage;
        try
        {
            responseMessage = await _openAIService.GetChatResponseAsync(request.Message, SystemPrompt);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to get response from Azure OpenAI, falling back to rule-based response");
            responseMessage = GenerateResponse(request.Message, intent);
        }

        return new ChatResponse
        {
            Message = responseMessage,
            SessionId = sessionId,
            Intent = intent,
            SuggestedFunds = suggestedFunds.Any() ? suggestedFunds : null,
            SuggestedQuestions = suggestedQuestions,
            Timestamp = DateTime.UtcNow
        };
    }

    private ChatIntent AnalyzeIntent(string message)
    {
        var messageLower = message.ToLower();
        var intent = new ChatIntent();

        if (messageLower.Contains("compare") || messageLower.Contains("comparison") ||
            messageLower.Contains("השווה") || messageLower.Contains("השוואה"))
        {
            intent.Type = "comparison";
        }
        else if (messageLower.Contains("recommend") || messageLower.Contains("suggest") ||
                 messageLower.Contains("המלץ") || messageLower.Contains("הצע"))
        {
            intent.Type = "recommendation";
        }
        else if (messageLower.Contains("fee") || messageLower.Contains("cost") ||
                 messageLower.Contains("עמלה") || messageLower.Contains("עלות") || messageLower.Contains("ניהול"))
        {
            intent.Type = "fee_inquiry";
        }
        else if (messageLower.Contains("return") || messageLower.Contains("performance") ||
                 messageLower.Contains("תשואה") || messageLower.Contains("ביצועים"))
        {
            intent.Type = "performance_inquiry";
        }
        else if (messageLower.Contains("risk") || messageLower.Contains("סיכון") ||
                 messageLower.Contains("שארפ") || messageLower.Contains("אלפא"))
        {
            intent.Type = "risk_inquiry";
        }
        else if (messageLower.Contains("גמל להשקעה") || messageLower.Contains("קופת גמל להשקעה"))
        {
            intent.Type = "gemel_general";
            intent.Parameters["fundType"] = "Gemel";
        }
        else if (messageLower.Contains("השתלמות") || messageLower.Contains("קרן השתלמות"))
        {
            intent.Type = "hishtalmut_general";
            intent.Parameters["fundType"] = "Hishtalmut";
        }
        else if (messageLower.Contains("חסכון לילד") || messageLower.Contains("גמל לילד"))
        {
            intent.Type = "gemel_child_general";
            intent.Parameters["fundType"] = "GemelChild";
        }
        else if (messageLower.Contains("גמל") || messageLower.Contains("provident"))
        {
            intent.Type = "gemel_general";
            intent.Parameters["fundType"] = "Gemel";
        }
        else if (messageLower.Contains("pension") || messageLower.Contains("פנסיה"))
        {
            intent.Type = "pension_general";
            intent.Parameters["fundType"] = "Pension";
        }
        else if (messageLower.Contains("executive") || messageLower.Contains("מנהלים"))
        {
            intent.Type = "executive_general";
            intent.Parameters["fundType"] = "Executive";
        }
        else
        {
            intent.Type = "general";
        }

        return intent;
    }

    private const string ResponseDisclaimer = "\n\n---\n⚠️ אתר זה אינו מספק ייעוץ פנסיוני. האתר מציג נתונים מאתר משרד האוצר בלבד. לקבלת ייעוץ פנסיוני יש לפנות לבעל רישיון מטעם משרד האוצר.";

    private string GenerateResponse(string message, ChatIntent intent)
    {
        var response = intent.Type switch
        {
            "comparison" => "ניתן להשוות בין קרנות פנסיה או ביטוחי מנהלים. איזה קרנות תרצה להשוות? ניתן לציין שמות ספציפיים או לבקש השוואה לפי קריטריונים כמו תשואה, דמי ניהול או סטיית תקן.",
            "recommendation" => "אינני יכול להמליץ על קרן ספציפית. לקבלת ייעוץ פנסיוני מותאם אישית יש לפנות לבעל רישיון ייעוץ פנסיוני מטעם משרד האוצר. אני יכול להציג נתונים על קרנות שונות - האם תרצה לראות השוואה?",
            "fee_inquiry" => "דמי הניהול משתנים בין הקרנות השונות. להלן נתוני דמי הניהול מאתר משרד האוצר. האם תרצה לראות רשימה של קרנות לפי דמי ניהול?",
            "performance_inquiry" => "להלן נתוני התשואות מאתר משרד האוצר. ניתן להציג נתונים לפי תקופה: שנה אחרונה, 3 שנים או 5 שנים. איזו תקופה מעניינת אותך?",
            "risk_inquiry" => "מדדי הסיכון כוללים סטיית תקן, מדד שארפ ואלפא. להלן הנתונים מאתר משרד האוצר. איזה מדד סיכון תרצה לראות?",
            "pension_general" => "להלן נתונים על קרנות פנסיה מאתר משרד האוצר. איזה נתונים תרצה לראות?",
            "executive_general" => "להלן נתונים על ביטוחי מנהלים מאתר משרד האוצר. איזה נתונים תרצה לראות?",
            "gemel_general" => "להלן נתונים על קופות גמל להשקעה מאתר משרד האוצר. ניתן להשוות תשואות, דמי ניהול ודמי הפקדה. איזה נתונים תרצה לראות?",
            "hishtalmut_general" => "להלן נתונים על קרנות השתלמות מאתר משרד האוצר. ניתן להשוות תשואות, דמי ניהול וביצועים. איזה נתונים תרצה לראות?",
            "gemel_child_general" => "להלן נתונים על קופות גמל לחסכון לילד מאתר משרד האוצר. איזה נתונים תרצה לראות?",
            _ => "שלום! אני כאן לעזור לך להציג ולהשוות נתונים על קרנות פנסיה, ביטוחי מנהלים, קופות גמל וקרנות השתלמות. אתה יכול לשאול אותי על השוואות ותשואות."
        };
        return response + ResponseDisclaimer;
    }

    private async Task<List<PensionFund>> GetRelevantFundsAsync(ChatIntent intent)
    {
        var fundType = intent.Parameters.ContainsKey("fundType") ? intent.Parameters["fundType"] : "Pension";
        // Add "nulls last" to avoid funds with null values appearing first
        var sortField = intent.Type switch
        {
            "fee_inquiry" => "AVG_ANNUAL_MANAGEMENT_FEE nulls last",
            "performance_inquiry" => "YEAR_TO_DATE_YIELD desc nulls last",
            "recommendation" => "YEAR_TO_DATE_YIELD desc nulls last",
            "risk_inquiry" => "SHARPE_RATIO desc nulls last",
            _ => "YEAR_TO_DATE_YIELD desc nulls last"
        };

        try
        {
            var funds = await FetchFundsFromApiAsync(fundType, sortField, 5);
            return funds;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error fetching funds from external API");
            return new List<PensionFund>();
        }
    }

    private async Task<List<PensionFund>> FetchFundsFromApiAsync(string fundType, string sort, int limit)
    {
        var apiKey = Environment.GetEnvironmentVariable("FUNDS_API_KEY") ?? "c01221ec-b769-47a7-883c-e6cfb01276ad";
        var apiFundType = fundType.ToLower() switch
        {
            "pension" => "Pension",
            "executive" or "insurance" => "Insurance",
            "gemel" or "hishtalmut" or "gemelchild" => "Provident",
            _ => "Pension"
        };

        // Build FUND_CLASSIFICATION filter for new fund types
        var classificationFilter = fundType.ToLower() switch
        {
            "gemel" => "{\"FUND_CLASSIFICATION\":{\"$eq\":\"קופת גמל להשקעה\"}}",
            "hishtalmut" => "{\"FUND_CLASSIFICATION\":{\"$eq\":\"קרנות השתלמות\"}}",
            "gemelchild" => "{\"FUND_CLASSIFICATION\":{\"$eq\":\"קופת גמל להשקעה - חסכון לילד\"}}",
            _ => null
        };

        var queryParams = $"fields={AllFields}&limit={limit}&sort={Uri.EscapeDataString(sort)}";
        if (!string.IsNullOrEmpty(classificationFilter))
        {
            queryParams += $"&complexFilters={Uri.EscapeDataString(classificationFilter)}";
        }

        var url = $"{ExternalApiBaseUrl}{ExternalApiPath}/{apiFundType}?{queryParams}";

        var request = new HttpRequestMessage(HttpMethod.Get, url);
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", apiKey);

        var response = await _httpClient.SendAsync(request);
        var content = await response.Content.ReadAsStringAsync();

        if (!response.IsSuccessStatusCode)
        {
            _logger.LogError("External API error: {StatusCode} - {Content}", response.StatusCode, content);
            return new List<PensionFund>();
        }

        var apiResult = JsonSerializer.Deserialize<ExternalApiResponse>(content, ApiJsonOptions);
        if (apiResult?.Success != true || apiResult.Result?.Records == null)
        {
            return new List<PensionFund>();
        }

        var mappedFundType = fundType.ToLower() switch
        {
            "executive" or "insurance" => "Executive",
            "gemel" => "Gemel",
            "hishtalmut" => "Hishtalmut",
            "gemelchild" => "GemelChild",
            _ => "Pension"
        };
        return apiResult.Result.Records.Select(r => MapToFund(r, mappedFundType)).ToList();
    }

    private static PensionFund MapToFund(ExternalFundRecord record, string fundType)
    {
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

    private List<string> GetSuggestedQuestions(ChatIntent intent)
    {
        return intent.Type switch
        {
            "comparison" => new List<string>
            {
                "השווה בין קרנות הפנסיה לפי תשואה",
                "הצג השוואת דמי ניהול בין קרנות"
            },
            "recommendation" => new List<string>
            {
                "הצג קרנות לפי תשואה גבוהה",
                "הצג קרנות לפי דמי ניהול נמוכים"
            },
            "fee_inquiry" => new List<string>
            {
                "הצג קרנות עם דמי ניהול נמוכים",
                "מה ההבדל בין דמי ניהול לדמי הפקדה?"
            },
            "risk_inquiry" => new List<string>
            {
                "מה זה מדד שארפ?",
                "הצג קרנות לפי מדד שארפ"
            },
            "gemel_general" => new List<string>
            {
                "הצג קופות גמל להשקעה עם תשואה גבוהה",
                "הצג קופות גמל עם דמי ניהול נמוכים"
            },
            "hishtalmut_general" => new List<string>
            {
                "הצג קרנות השתלמות עם תשואה גבוהה ב-5 שנים",
                "השווה בין קרנות השתלמות לפי דמי ניהול"
            },
            "gemel_child_general" => new List<string>
            {
                "הצג קופות חסכון לילד עם תשואה גבוהה",
                "השווה בין קופות חסכון לילד"
            },
            _ => new List<string>
            {
                "מי החמש חברות שלהן תשואה הגבוהה ביותר במסלול 50 ומטה?",
                "תציג לי את ה 3 חברות שלהן קרן פנסיה מקיפה במסלול השקעה מניות",
                "הצג קרנות השתלמות עם תשואה גבוהה",
                "הצג קופות גמל להשקעה לפי דמי ניהול"
            }
        };
    }
}
