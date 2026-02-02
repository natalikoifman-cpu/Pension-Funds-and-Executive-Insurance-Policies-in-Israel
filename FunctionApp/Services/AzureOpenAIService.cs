using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;

namespace FunctionApp.Services;

public interface IAzureOpenAIService
{
    Task<string> GetChatResponseAsync(string userMessage, string systemPrompt);
}

public class AzureOpenAIService : IAzureOpenAIService
{
    private readonly HttpClient _httpClient;
    private readonly string _endpoint;
    private readonly string _deployment;

    public AzureOpenAIService()
    {
        _endpoint = Environment.GetEnvironmentVariable("AZURE_OPENAI_ENDPOINT")
            ?? throw new InvalidOperationException("AZURE_OPENAI_ENDPOINT is not configured");
        var apiKey = Environment.GetEnvironmentVariable("AZURE_OPENAI_API_KEY")
            ?? throw new InvalidOperationException("AZURE_OPENAI_API_KEY is not configured");
        _deployment = Environment.GetEnvironmentVariable("AZURE_OPENAI_DEPLOYMENT") ?? "gpt-4o";

        _httpClient = new HttpClient();
        _httpClient.DefaultRequestHeaders.Add("api-key", apiKey);
    }

    public async Task<string> GetChatResponseAsync(string userMessage, string systemPrompt)
    {
        var requestBody = new
        {
            messages = new[]
            {
                new { role = "system", content = systemPrompt },
                new { role = "user", content = userMessage }
            },
            max_tokens = 1000,
            temperature = 0.7
        };

        var json = JsonSerializer.Serialize(requestBody);
        var content = new StringContent(json, Encoding.UTF8, "application/json");

        // Azure AI Foundry endpoint format
        var url = $"{_endpoint.TrimEnd('/')}/openai/deployments/{_deployment}/chat/completions?api-version=2024-06-01";

        var response = await _httpClient.PostAsync(url, content);
        response.EnsureSuccessStatusCode();

        var responseJson = await response.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(responseJson);

        return doc.RootElement
            .GetProperty("choices")[0]
            .GetProperty("message")
            .GetProperty("content")
            .GetString() ?? "מצטער, לא הצלחתי לעבד את הבקשה.";
    }
}
