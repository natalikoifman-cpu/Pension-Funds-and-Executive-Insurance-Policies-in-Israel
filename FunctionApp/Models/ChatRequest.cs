namespace FunctionApp.Models;

public class ChatRequest
{
    public string Message { get; set; } = string.Empty;
    public string? SessionId { get; set; }
    public string? UserId { get; set; }
    public ChatContext? Context { get; set; }
}

public class ChatContext
{
    public List<ChatMessage> History { get; set; } = new();
    public string? CurrentFundId { get; set; }
    public string? UserPreferences { get; set; }
}

public class ChatMessage
{
    public string Role { get; set; } = string.Empty;
    public string Content { get; set; } = string.Empty;
    public DateTime Timestamp { get; set; }
}
