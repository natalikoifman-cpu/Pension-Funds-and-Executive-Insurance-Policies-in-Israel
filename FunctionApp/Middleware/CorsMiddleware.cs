using System.Net;
using Microsoft.Azure.Functions.Worker;
using Microsoft.Azure.Functions.Worker.Http;
using Microsoft.Azure.Functions.Worker.Middleware;

public class CorsMiddleware : IFunctionsWorkerMiddleware
{
    private static readonly HashSet<string> AllowedOrigins = new(StringComparer.OrdinalIgnoreCase)
    {
        "https://pension-funds-and-executive-insurance.onrender.com",
        "https://ashy-coast-0e8e3620f.4.azurestaticapps.net",
        "https://portal.azure.com"
    };

    public async Task Invoke(FunctionContext context, FunctionExecutionDelegate next)
    {
        var request = await context.GetHttpRequestDataAsync();
        var origin = request?.Headers.TryGetValues("Origin", out var origins) == true
            ? origins.FirstOrDefault()
            : null;

        // Handle preflight OPTIONS requests
        if (request != null && string.Equals(request.Method, "OPTIONS", StringComparison.OrdinalIgnoreCase))
        {
            var preflightResponse = request.CreateResponse(HttpStatusCode.OK);
            SetCorsHeaders(preflightResponse, origin);
            context.GetInvocationResult().Value = preflightResponse;
            return;
        }

        await next(context);

        // Add CORS headers to the actual response
        var response = context.GetHttpResponseData();
        if (response != null)
        {
            SetCorsHeaders(response, origin);
        }
    }

    private static void SetCorsHeaders(HttpResponseData response, string? origin)
    {
        if (origin != null && AllowedOrigins.Contains(origin))
        {
            response.Headers.Add("Access-Control-Allow-Origin", origin);
            response.Headers.Add("Access-Control-Allow-Credentials", "true");
        }
        response.Headers.Add("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
        response.Headers.Add("Access-Control-Allow-Headers", "Content-Type, Authorization");
    }
}
