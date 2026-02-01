using Microsoft.Azure.Functions.Worker;
using Microsoft.Extensions.Logging;

namespace FunctionApp.EntraADSync;

public class EntraADSyncFunction
{
    private readonly ILogger<EntraADSyncFunction> _logger;

    public EntraADSyncFunction(ILogger<EntraADSyncFunction> logger)
    {
        _logger = logger;
    }

    [Function("SyncFunction")]
    public async Task Run([TimerTrigger("%ENTRA_AD_SYNC_SCHEDULE%")] TimerInfo myTimer)
    {
        _logger.LogInformation("Entra AD Sync function started at: {time}", DateTime.UtcNow);

        try
        {
            await SyncUsersFromEntraADAsync();
            _logger.LogInformation("Entra AD Sync completed successfully at: {time}", DateTime.UtcNow);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Entra AD Sync failed at: {time}", DateTime.UtcNow);
            throw;
        }

        if (myTimer.ScheduleStatus is not null)
        {
            _logger.LogInformation("Next sync scheduled at: {next}", myTimer.ScheduleStatus.Next);
        }
    }

    private async Task SyncUsersFromEntraADAsync()
    {
        // In production, this would:
        // 1. Connect to Microsoft Graph API
        // 2. Fetch users from Entra AD
        // 3. Update local user database

        _logger.LogInformation("Simulating Entra AD user sync...");
        await Task.Delay(100); // Placeholder for actual sync operation
        _logger.LogInformation("User sync simulation completed");
    }
}
