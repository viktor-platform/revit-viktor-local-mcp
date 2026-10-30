using Autodesk.Revit.DB.Events;
using Autodesk.Revit.UI;
using RevitMcp.RevitAddin.Bridge;
using RevitMcp.RevitAddin.Handlers;
using System;
using System.IO;
using System.Reflection;

namespace RevitMcp.RevitAddin;

public sealed class App : IExternalApplication
{
    private BridgeRequestBroker? _broker;
    private PushButton? _toggleButton;
    private AdapterSettings _settings = new();

    internal static App? Current { get; private set; }

    internal int Port => _settings.Port;

    internal bool IsRunning => Bridge is not null;

    public Result OnStartup(UIControlledApplication application)
    {
#if NETFRAMEWORK
        AppDomain.CurrentDomain.AssemblyResolve += ResolveBundledAssembly;
#endif
        Current = this;
        try
        {
            _settings = AdapterSettings.Load();
        }
        catch (Exception ex)
        {
            _settings = new AdapterSettings { Enabled = false };
            Autodesk.Revit.UI.TaskDialog.Show("Revit Adapter", $"Could not load adapter settings: {ex.Message}\nThe adapter is disabled. Correct or remove {AdapterSettings.FilePath}, then restart Revit.");
        }

        var panel = application.CreateRibbonPanel("Revit Adapter");
        var assembly = Assembly.GetExecutingAssembly().Location;
        var portButton = panel.AddItem(new PushButtonData(
            "RevitAdapterPort",
            "Update\nPort",
            assembly,
            typeof(UpdateAdapterPortCommand).FullName)) as PushButton;
        if (portButton is not null)
        {
            portButton.LargeImage = AdapterRibbonIcons.Port(32);
            portButton.Image = AdapterRibbonIcons.Port(16);
            portButton.ToolTip = "Change the local Revit adapter port.";
        }

        _toggleButton = panel.AddItem(new PushButtonData(
            "RevitAdapterToggle",
            "Start\nadapter",
            assembly,
            typeof(ToggleAdapterCommand).FullName)) as PushButton;
        RefreshRibbonState();

        application.ControlledApplication.ApplicationInitialized += OnApplicationInitialized;
        return Result.Succeeded;
    }

    public Result OnShutdown(UIControlledApplication application)
    {
        application.ControlledApplication.ApplicationInitialized -= OnApplicationInitialized;
        StopBridge();
        _broker?.Dispose();
        _broker = null;
        _toggleButton = null;
        Current = null;
#if NETFRAMEWORK
        AppDomain.CurrentDomain.AssemblyResolve -= ResolveBundledAssembly;
#endif
        return Result.Succeeded;
    }

    internal void SetEnabled(bool enabled)
    {
        if (enabled == IsRunning)
        {
            return;
        }

        if (enabled)
        {
            StartBridge(_settings.Port);
            _settings.Enabled = true;
        }
        else
        {
            StopBridge();
            _settings.Enabled = false;
        }

        _settings.Save();
    }

    internal void UpdatePort(int port)
    {
        AdapterSettings.ValidatePort(port);
        if (port == _settings.Port)
        {
            return;
        }

        var oldPort = _settings.Port;
        if (IsRunning)
        {
            StopBridge();
            try
            {
                StartBridge(port);
            }
            catch
            {
                StartBridge(oldPort);
                throw;
            }
        }

        _settings.Port = port;
        _settings.Save();
    }

    private void OnApplicationInitialized(object? sender, ApplicationInitializedEventArgs args)
    {
        var dispatcher = new CommandDispatcher(new IRevitCommandHandler[]
        {
            // Register every new handler here. The name must match the MCP tool name.
            new GetModelNameHandler(),
            new ListCategoriesHandler()
        });

        _broker = new BridgeRequestBroker(dispatcher);
        if (_settings.Enabled)
        {
            try
            {
                StartBridge(_settings.Port);
            }
            catch (Exception ex)
            {
                _settings.Enabled = false;
                Autodesk.Revit.UI.TaskDialog.Show("Revit Adapter", $"Could not start the adapter on port {_settings.Port}: {ex.Message}\nUse the ribbon control to retry after resolving the port conflict.");
            }
        }
    }

    private void StartBridge(int port)
    {
        if (_broker is null)
        {
            throw new InvalidOperationException("Revit adapter is not initialized yet.");
        }

        var bridge = new LocalHttpBridge(_broker);
        try
        {
            bridge.Start($"http://127.0.0.1:{port}/");
            Bridge = bridge;
            RefreshRibbonState();
        }
        catch
        {
            bridge.Dispose();
            throw;
        }
    }

    private void StopBridge()
    {
        Bridge?.Dispose();
        Bridge = null;
        RefreshRibbonState();
    }

    private void RefreshRibbonState()
    {
        if (_toggleButton is null)
        {
            return;
        }

        _toggleButton.ItemText = IsRunning ? "Stop\nadapter" : "Start\nadapter";
        _toggleButton.LargeImage = IsRunning ? AdapterRibbonIcons.Running(32) : AdapterRibbonIcons.Stopped(32);
        _toggleButton.Image = IsRunning ? AdapterRibbonIcons.Running(16) : AdapterRibbonIcons.Stopped(16);
        _toggleButton.ToolTip = IsRunning
            ? $"Stop the Revit adapter listening on 127.0.0.1:{Port}."
            : $"Start the Revit adapter on 127.0.0.1:{Port}.";
    }

#if NETFRAMEWORK
    private static Assembly? ResolveBundledAssembly(object? sender, ResolveEventArgs args)
    {
        var requested = new AssemblyName(args.Name);
        if (string.IsNullOrEmpty(requested.Name) || requested.Name.EndsWith(".resources", StringComparison.OrdinalIgnoreCase))
        {
            return null;
        }

        var directory = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
        if (string.IsNullOrEmpty(directory))
        {
            return null;
        }

        var candidate = Path.Combine(directory, requested.Name + ".dll");
        if (!File.Exists(candidate) || !string.Equals(
                AssemblyName.GetAssemblyName(candidate).Name,
                requested.Name,
                StringComparison.OrdinalIgnoreCase))
        {
            return null;
        }

        return Assembly.LoadFrom(candidate);
    }
#endif

    internal static LocalHttpBridge? Bridge { get; private set; }
}
