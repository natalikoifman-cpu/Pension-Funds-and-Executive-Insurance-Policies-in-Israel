using System.ClientModel;
using Azure.AI.OpenAI;
using OpenAI.Chat;

namespace FunctionApp.Services;

public interface IAzureOpenAIService
{
    Task<string> GetChatResponseAsync(string userMessage, string systemPrompt);
}

public class AzureOpenAIService : IAzureOpenAIService
{
    private readonly ChatClient _chatClient;

    public AzureOpenAIService()
    {
        var endpoint = Environment.GetEnvironmentVariable("AZURE_OPENAI_ENDPOINT")
            ?? throw new InvalidOperationException("AZURE_OPENAI_ENDPOINT is not configured");
        var apiKey = Environment.GetEnvironmentVariable("AZURE_OPENAI_API_KEY")
            ?? throw new InvalidOperationException("AZURE_OPENAI_API_KEY is not configured");
        var deployment = Environment.GetEnvironmentVariable("AZURE_OPENAI_DEPLOYMENT") ?? "gpt-4o";

        var client = new AzureOpenAIClient(new Uri(endpoint), new ApiKeyCredential(apiKey));
        _chatClient = client.GetChatClient(deployment);
    }

    public async Task<string> GetChatResponseAsync(string userMessage, string systemPrompt)
    {
        var messages = new List<ChatMessage>
        {
            new SystemChatMessage(systemPrompt),
            new UserChatMessage(userMessage)
        };

        var response = await _chatClient.CompleteChatAsync(messages);
        return response.Value.Content[0].Text;
    }
}
