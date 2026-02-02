using System.Net;
using System.Text.Json;
using FunctionApp.Models;
using FunctionApp.Services;
using Microsoft.Azure.Functions.Worker;
using Microsoft.Azure.Functions.Worker.Http;
using Microsoft.Extensions.Logging;

namespace FunctionApp.Chat;

public class ChatFunction
{
    private readonly ILogger<ChatFunction> _logger;
    private readonly IAzureOpenAIService _openAIService;

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

נתוני קרנות לדוגמה שיש לך מידע עליהם:
- מיטב דש גמל: תשואה 8.5%, דמי ניהול 0.5%, סיכון בינוני
- הראל פנסיה: תשואה 7.8%, דמי ניהול 0.45%, סיכון נמוך
- מנורה מבטחים פנסיה: תשואה 9.2%, דמי ניהול 0.55%, סיכון גבוה
- כלל ביטוח מנהלים: תשואה 6.5%, דמי ניהול 0.6%, סיכון נמוך
- פניקס ביטוח מנהלים: תשואה 7.2%, דמי ניהול 0.52%, סיכון בינוני";

    public ChatFunction(ILogger<ChatFunction> logger, IAzureOpenAIService openAIService)
    {
        _logger = logger;
        _openAIService = openAIService;
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
        await response.WriteAsJsonAsync(chatResponse);
        return response;
    }

    private async Task<ChatResponse> ProcessChatAsync(ChatRequest request)
    {
        var sessionId = request.SessionId ?? Guid.NewGuid().ToString();
        var intent = AnalyzeIntent(request.Message);
        var suggestedFunds = GetRelevantFunds(intent);
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
                 messageLower.Contains("עמלה") || messageLower.Contains("עלות"))
        {
            intent.Type = "fee_inquiry";
        }
        else if (messageLower.Contains("return") || messageLower.Contains("performance") ||
                 messageLower.Contains("תשואה") || messageLower.Contains("ביצועים"))
        {
            intent.Type = "performance_inquiry";
        }
        else if (messageLower.Contains("risk") || messageLower.Contains("סיכון"))
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
            "fee_inquiry" => "דמי הניהול משתנים בין הקרנות השונות. בדרך כלל נעים בין 0.25% ל-1.5%. האם תרצה לראות רשימה של קרנות עם דמי הניהול הנמוכים ביותר?",
            "performance_inquiry" => "התשואות של קרנות הפנסיה וביטוחי המנהלים משתנות לפי תקופה ורמת סיכון. האם תרצה לראות את הקרנות עם התשואות הגבוהות ביותר בשנה האחרונה?",
            "risk_inquiry" => "רמת הסיכון היא פרמטר חשוב בבחירת קרן. קרנות עם סיכון גבוה יותר עשויות להניב תשואות גבוהות יותר לאורך זמן, אך גם להפסיד יותר בתקופות קשות. מה רמת הסיכון המועדפת עליך - נמוכה, בינונית או גבוהה?",
            "pension_general" => "קרנות פנסיה הן מכשיר חיסכון ארוך טווח לפרישה. יש לנו מידע על מגוון קרנות פנסיה. במה אוכל לעזור לך?",
            "executive_general" => "ביטוח מנהלים הוא מוצר פנסיוני המשלב חיסכון עם כיסויים ביטוחיים. יש לנו מידע על מגוון ביטוחי מנהלים. במה אוכל לעזור לך?",
            _ => "שלום! אני כאן לעזור לך למצוא את קרן הפנסיה או ביטוח המנהלים המתאים לך. אתה יכול לשאול אותי על השוואות בין קרנות, תשואות, דמי ניהול, או לבקש המלצות מותאמות אישית."
        };
    }

    private List<PensionFund> GetRelevantFunds(ChatIntent intent)
    {
        var allFunds = GetSampleFunds();

        return intent.Type switch
        {
            "fee_inquiry" => allFunds.OrderBy(f => f.ManagementFee).Take(3).ToList(),
            "performance_inquiry" => allFunds.OrderByDescending(f => f.AnnualReturn).Take(3).ToList(),
            "risk_inquiry" => allFunds.Where(f => f.RiskLevel == "Low").Take(3).ToList(),
            "pension_general" => allFunds.Where(f => f.FundType == "Pension").Take(3).ToList(),
            "executive_general" => allFunds.Where(f => f.FundType == "Executive").Take(3).ToList(),
            _ => new List<PensionFund>()
        };
    }

    private List<string> GetSuggestedQuestions(ChatIntent intent)
    {
        return intent.Type switch
        {
            "comparison" => new List<string>
            {
                "השווה בין מיטב דש לבין הראל פנסיה",
                "איזו קרן עדיפה מבחינת תשואה?",
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
            _ => new List<string>
            {
                "השווה בין קרנות פנסיה",
                "המלץ לי על קרן פנסיה",
                "מהם דמי הניהול הממוצעים?",
                "איזו קרן מניבה את התשואה הגבוהה ביותר?"
            }
        };
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
}
