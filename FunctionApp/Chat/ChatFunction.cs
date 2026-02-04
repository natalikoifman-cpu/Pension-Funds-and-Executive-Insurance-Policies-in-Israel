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

    private const string SystemPrompt = @"אתה יועץ פנסיוני מומחה בישראל. תפקידך לעזור למשתמשים להבין ולהשוות בין קרנות פנסיה וביטוחי מנהלים.

כללים:
1. ענה תמיד בעברית אלא אם המשתמש פונה באנגלית
2. היה מדויק ומקצועי אך ידידותי
3. הסבר מושגים פיננסיים בצורה פשוטה
4. אם אתה לא בטוח במשהו, ציין זאת
5. המלץ תמיד להתייעץ עם יועץ פנסיוני מוסמך לפני קבלת החלטות

נושאים שאתה מומחה בהם:
- קרנות פנסיה (Pension Funds)
- ביטוחי מנהלים (Executive Insurance)
- קופות גמל (Savings Funds)
- דמי ניהול והשוואת עלויות
- תשואות ורמות סיכון
- זכויות עובדים ומעסיקים

יש לך גישה לנתונים עדכניים על מאות קרנות פנסיה וביטוחי מנהלים בישראל, כולל:
- תשואות (חודשית, שנתית, 3 שנים, 5 שנים)
- דמי ניהול ודמי הפקדה
- מדדי סיכון (סטיית תקן, שארפ, אלפא)
- חשיפה למניות, לחו""ל ולמט""ח";

    public ChatFunction(ILogger<ChatFunction> logger, IAzureOpenAIService openAIService, IHttpClientFactory httpClientFactory)
    {
        _logger = logger;
        _openAIService = openAIService;
        _httpClient = httpClientFactory.CreateClient();
    }

    [Function("Chat")]
    public async Task<HttpResponseData> Run(
        [HttpTrigger(AuthorizationLevel.Anonymous, "post")] HttpRequestData req)
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

    private string GenerateResponse(string message, ChatIntent intent)
    {
        return intent.Type switch
        {
            "comparison" => "אשמח לעזור לך להשוות בין קרנות פנסיה או ביטוחי מנהלים. איזה קרנות תרצה להשוות? אתה יכול לציין שמות ספציפיים או לבקש השוואה לפי קריטריונים כמו תשואה, דמי ניהול או רמת סיכון.",
            "recommendation" => "כדי להמליץ לך על קרן מתאימה, אצטרך לדעת קצת יותר על הצרכים שלך. מה חשוב לך יותר - תשואה גבוהה, דמי ניהול נמוכים, או רמת סיכון נמוכה?",
            "fee_inquiry" => "דמי הניהול משתנים בין הקרנות השונות. בדרך כלל נעים בין 0.1% ל-1.5%. האם תרצה לראות רשימה של קרנות עם דמי הניהול הנמוכים ביותר?",
            "performance_inquiry" => "התשואות של קרנות הפנסיה וביטוחי המנהלים משתנות לפי תקופה ורמת סיכון. האם תרצה לראות את הקרנות עם התשואות הגבוהות ביותר בשנה האחרונה, 3 שנים או 5 שנים?",
            "risk_inquiry" => "רמת הסיכון היא פרמטר חשוב בבחירת קרן. קרנות עם סיכון גבוה יותר עשויות להניב תשואות גבוהות יותר לאורך זמן, אך גם להפסיד יותר בתקופות קשות. מדדי הסיכון כוללים סטיית תקן, מדד שארפ ואלפא. מה רמת הסיכון המועדפת עליך?",
            "pension_general" => "קרנות פנסיה הן מכשיר חיסכון ארוך טווח לפרישה. יש לנו מידע על מאות קרנות פנסיה. במה אוכל לעזור לך?",
            "executive_general" => "ביטוח מנהלים הוא מוצר פנסיוני המשלב חיסכון עם כיסויים ביטוחיים. יש לנו מידע על מאות ביטוחי מנהלים. במה אוכל לעזור לך?",
            _ => "שלום! אני כאן לעזור לך למצוא את קרן הפנסיה או ביטוח המנהלים המתאים לך. אתה יכול לשאול אותי על השוואות בין קרנות, תשואות, דמי ניהול, או לבקש המלצות מותאמות אישית."
        };
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
            _ => "Pension"
        };

        var url = $"{ExternalApiBaseUrl}{ExternalApiPath}/{apiFundType}?fields={AllFields}&limit={limit}&sort={Uri.EscapeDataString(sort)}";

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

        var mappedFundType = apiFundType == "Insurance" ? "Executive" : "Pension";
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
                "השווה בין קרנות הפנסיה המובילות",
                "איזו קרן עדיפה מבחינת תשואה ל-5 שנים?",
                "איזו קרן עדיפה מבחינת דמי ניהול?"
            },
            "recommendation" => new List<string>
            {
                "מהן הקרנות עם התשואה הגבוהה ביותר?",
                "מהן הקרנות עם דמי הניהול הנמוכים ביותר?",
                "איזו קרן מתאימה לסיכון נמוך?"
            },
            "fee_inquiry" => new List<string>
            {
                "מה ההבדל בין דמי ניהול לדמי הפקדה?",
                "איך דמי הניהול משפיעים על החיסכון שלי?",
                "האם ניתן להפחית את דמי הניהול?"
            },
            "risk_inquiry" => new List<string>
            {
                "מה זה מדד שארפ?",
                "מה זה אלפא?",
                "איך בוחרים קרן לפי רמת סיכון?"
            },
            _ => new List<string>
            {
                "השווה בין קרנות פנסיה",
                "המלץ לי על קרן פנסיה",
                "מהם דמי הניהול הממוצעים?",
                "איזו קרן מניבה את התשואה הגבוהה ביותר?"
            }
        };
    }
}
