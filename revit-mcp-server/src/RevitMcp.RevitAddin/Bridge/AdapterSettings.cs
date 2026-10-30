using System;
using System.IO;
using System.Text.Json;

namespace RevitMcp.RevitAddin.Bridge;

internal sealed class AdapterSettings
{
    public const int DefaultPort = 5057;

    public int Port { get; set; } = DefaultPort;

    public bool Enabled { get; set; } = true;

    public static string FilePath => Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "RevitMcp",
        "adapter-settings.json");

    public static AdapterSettings Load()
    {
        if (!File.Exists(FilePath))
        {
            return new AdapterSettings();
        }

        var settings = JsonSerializer.Deserialize<AdapterSettings>(File.ReadAllText(FilePath))
            ?? throw new InvalidDataException("Adapter settings are empty.");
        ValidatePort(settings.Port);
        return settings;
    }

    public void Save()
    {
        ValidatePort(Port);
        var directory = Path.GetDirectoryName(FilePath)
            ?? throw new InvalidOperationException("Adapter settings path is invalid.");
        Directory.CreateDirectory(directory);
        File.WriteAllText(FilePath, JsonSerializer.Serialize(this, new JsonSerializerOptions
        {
            WriteIndented = true
        }));
    }

    public static void ValidatePort(int port)
    {
        if (port < 1024 || port > 65535)
        {
            throw new ArgumentOutOfRangeException(nameof(port), "Port must be between 1024 and 65535.");
        }
    }
}
