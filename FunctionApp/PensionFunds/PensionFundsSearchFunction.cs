using Microsoft.Azure.Functions.Worker;
using Microsoft.Azure.Functions.Worker.Http;
using Microsoft.Extensions.Logging;
using System.Net;
using System.Text.Json;

namespace FunctionApp.PensionFunds
{
    public class PensionFundsSearchFunction
    {
        private readonly ILogger<PensionFundsSearchFunction> _logger;

        public PensionFundsSearchFunction(ILogger<PensionFundsSearchFunction> logger)
        {
            _logger = logger;
        }

        [Function("PensionFundsSearch")]
        public async Task<HttpResponseData> Run(
            [HttpTrigger(AuthorizationLevel.Function, "get", Route = "pension-funds/search")]
            HttpRequestData req)
        {
            _logger.LogInformation("PensionFundsSearch function triggered");

            // Parse query parameters
            var query = System.Web.HttpUtility.ParseQueryString(req.Url.Query);
            var fundName = query["fundName"];
            var productType = query["productType"]; // "pension" or "insurance"
            var sortBy = query["sortBy"];
            var fundType = query["fundType"];
            var establishmentPeriod = query["establishmentPeriod"];

            // TODO: Implement search logic against Ministry of Finance data
            // For now, return sample response

            var response = req.CreateResponse(HttpStatusCode.OK);
            response.Headers.Add("Content-Type", "application/json; charset=utf-8");

            await response.WriteStringAsync(JsonSerializer.Serialize(new
            {
                success = true,
                count = 0,
                results = new List<object>()
            }));

            return response;
        }
    }
}
