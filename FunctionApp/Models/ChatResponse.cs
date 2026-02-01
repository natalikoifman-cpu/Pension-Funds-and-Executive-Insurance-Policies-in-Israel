namespace FunctionApp.Models;

public class ChatResponse
{
    public string Message { get; set; } = string.Empty;
    public string SessionId { get; set; } = string.Empty;
    public ChatIntent? Intent { get; set; }
    public List<PensionFund>? SuggestedFunds { get; set; }
    public List<string>? SuggestedQuestions { get; set; }
    public DateTime Timestamp { get; set; }
}

public class ChatIntent
{
    public string Type { get; set; } = string.Empty;
    public Dictionary<string, string> Parameters { get; set; } = new();
}
