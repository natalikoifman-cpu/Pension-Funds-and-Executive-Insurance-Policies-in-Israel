using Microsoft.Azure.Functions.Worker;
using Microsoft.Azure.Functions.Worker.Http;
using Microsoft.Extensions.Logging;
using System.Net;
using System.Text.Json;

namespace FunctionApp.PensionFunds
{
    public class PensionFundsChatFunction
    {
        private readonly ILogger<PensionFundsChatFunction> _logger;

        public PensionFundsChatFunction(ILogger<PensionFundsChatFunction> logger)
        {
            _logger = logger;
        }

        [Function("PensionFundsChat")]
        public async Task<HttpResponseData> Run(
            [HttpTrigger(AuthorizationLevel.Function, "post", Route = "pension-funds/chat")]
            HttpRequestData req)
        {
            _logger.LogInformation("PensionFundsChat function triggered");

            // Read request body
            string requestBody = await new StreamReader(req.Body).ReadToEndAsync();
            var chatRequest = JsonSerializer.Deserialize<PensionFundsChatRequest>(requestBody, new JsonSerializerOptions
            {
                PropertyNameCaseInsensitive = true
            });

            // TODO: Implement chat logic with AI/LLM
            // - Query pension funds data
            // - Generate response
            // - Add disclaimer

            var disclaimer = @"
⚠️ אתר זה אינו מספק ייעוץ פנסיוני.
האתר מציג נתונים מאתר משרד האוצר בלבד.
לקבלת ייעוץ פנסיוני יש לפנות לבעל רישיון מטעם משרד האוצר.";

            var response = req.CreateResponse(HttpStatusCode.OK);
            response.Headers.Add("Content-Type", "application/json; charset=utf-8");

            await response.WriteStringAsync(JsonSerializer.Serialize(new
            {
                success = true,
                message = "תשובה לשאלה שלך...",
                disclaimer = disclaimer,
                funds = new List<object>()
            }));

            return response;
        }
    }

    public class PensionFundsChatRequest
    {
        public string Message { get; set; }
        public List<PensionFundsChatMessage>? History { get; set; }
    }

    public class PensionFundsChatMessage
    {
        public string Role { get; set; }
        public string Content { get; set; }
    }
}
