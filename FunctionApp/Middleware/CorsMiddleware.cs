using System.Net;
using Microsoft.Azure.Functions.Worker;
using Microsoft.Azure.Functions.Worker.Http;
using Microsoft.Azure.Functions.Worker.Middleware;

public class CorsMiddleware : IFunctionsWorkerMiddleware
{
    private const string AllowedOrigin = "*";

    public async Task Invoke(FunctionContext context, FunctionExecutionDelegate next)
    {
        var request = await context.GetHttpRequestDataAsync();

        // Handle preflight OPTIONS requests
        if (request != null && string.Equals(request.Method, "OPTIONS", StringComparison.OrdinalIgnoreCase))
        {
            var preflightResponse = request.CreateResponse(HttpStatusCode.OK);
            SetCorsHeaders(preflightResponse);
            context.GetInvocationResult().Value = preflightResponse;
            return;
        }

        await next(context);

        // Add CORS headers to the actual response
        var response = context.GetHttpResponseData();
        if (response != null)
        {
            SetCorsHeaders(response);
        }
    }

    private static void SetCorsHeaders(HttpResponseData response)
    {
        response.Headers.Add("Access-Control-Allow-Origin", AllowedOrigin);
        response.Headers.Add("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
        response.Headers.Add("Access-Control-Allow-Headers", "Content-Type, Authorization");
    }
}
