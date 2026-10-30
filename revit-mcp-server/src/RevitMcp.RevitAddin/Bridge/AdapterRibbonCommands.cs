using Autodesk.Revit.Attributes;
using Autodesk.Revit.DB;
using Autodesk.Revit.UI;
using System;
using System.Windows.Forms;

namespace RevitMcp.RevitAddin.Bridge;

[Transaction(TransactionMode.Manual)]
public sealed class UpdateAdapterPortCommand : IExternalCommand
{
    public Result Execute(ExternalCommandData commandData, ref string message, ElementSet elements)
    {
        var app = App.Current;
        if (app is null)
        {
            message = "Revit adapter is not initialized.";
            return Result.Failed;
        }

        using var dialog = new System.Windows.Forms.Form
        {
            Text = "Revit Adapter Port",
            Width = 340,
            Height = 170,
            FormBorderStyle = FormBorderStyle.FixedDialog,
            StartPosition = FormStartPosition.CenterScreen,
            MinimizeBox = false,
            MaximizeBox = false
        };
        var prompt = new Label
        {
            Left = 18,
            Top = 18,
            Width = 290,
            Text = "Local adapter port (default 5057):"
        };
        var portInput = new NumericUpDown
        {
            Left = 18,
            Top = 44,
            Width = 290,
            Minimum = 1024,
            Maximum = 65535,
            Value = app.Port
        };
        var save = new Button
        {
            Text = "Save",
            Left = 150,
            Top = 82,
            Width = 75,
            DialogResult = DialogResult.OK
        };
        var cancel = new Button
        {
            Text = "Cancel",
            Left = 233,
            Top = 82,
            Width = 75,
            DialogResult = DialogResult.Cancel
        };
        dialog.Controls.AddRange(new System.Windows.Forms.Control[] { prompt, portInput, save, cancel });
        dialog.AcceptButton = save;
        dialog.CancelButton = cancel;
        if (dialog.ShowDialog() != DialogResult.OK)
        {
            return Result.Cancelled;
        }

        try
        {
            app.UpdatePort((int)portInput.Value);
            Autodesk.Revit.UI.TaskDialog.Show("Revit Adapter", $"Adapter port is now {app.Port}. If you changed it from 5057, set REVIT_MCP_BRIDGE_URL for the external MCP server and restart that server.");
            return Result.Succeeded;
        }
        catch (Exception ex)
        {
            message = ex.Message;
            return Result.Failed;
        }
    }
}

[Transaction(TransactionMode.Manual)]
public sealed class ToggleAdapterCommand : IExternalCommand
{
    public Result Execute(ExternalCommandData commandData, ref string message, ElementSet elements)
    {
        var app = App.Current;
        if (app is null)
        {
            message = "Revit adapter is not initialized.";
            return Result.Failed;
        }

        try
        {
            app.SetEnabled(!app.IsRunning);
            var status = app.IsRunning ? $"active on 127.0.0.1:{app.Port}" : "deactivated";
            Autodesk.Revit.UI.TaskDialog.Show("Revit Adapter", $"Adapter {status}. This preference is saved for the next Revit launch.");
            return Result.Succeeded;
        }
        catch (Exception ex)
        {
            message = ex.Message;
            return Result.Failed;
        }
    }
}
