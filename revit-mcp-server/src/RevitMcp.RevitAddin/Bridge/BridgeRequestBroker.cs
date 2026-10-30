using Autodesk.Revit.UI;
using System.Collections.Concurrent;
using System.Text.Json;

namespace RevitMcp.RevitAddin.Bridge;

internal sealed class BridgeRequestBroker : IDisposable
{
    private readonly CommandDispatcher _dispatcher;
    private readonly ConcurrentQueue<PendingBridgeRequest> _queue = new();
    private readonly BridgeExternalEventHandler _handler;
    private readonly ExternalEvent _externalEvent;
    private bool _disposed;

    public BridgeRequestBroker(CommandDispatcher dispatcher)
    {
        _dispatcher = dispatcher;
        _handler = new BridgeExternalEventHandler(ProcessQueue);
        _externalEvent = ExternalEvent.Create(_handler);
    }

    public Task<object?> InvokeAsync(string tool, JsonElement arguments)
    {
        ThrowIfDisposed();

        var pending = new PendingBridgeRequest(tool, arguments.Clone());
        _queue.Enqueue(pending);

        var raiseRequest = _externalEvent.Raise();
        if (raiseRequest is not ExternalEventRequest.Accepted and not ExternalEventRequest.Pending)
        {
            pending.TrySetException(new InvalidOperationException($"Failed to schedule Revit command. ExternalEvent returned {raiseRequest}."));
        }

        return pending.Task;
    }

    public void Dispose()
    {
        if (_disposed)
        {
            return;
        }

        _disposed = true;

        while (_queue.TryDequeue(out var pending))
        {
            pending.TrySetException(new ObjectDisposedException(nameof(BridgeRequestBroker)));
        }

        _externalEvent.Dispose();
    }

    private void ProcessQueue(UIApplication uiApp)
    {
        while (_queue.TryDequeue(out var pending))
        {
            if (pending.Task.IsCompleted)
            {
                continue;
            }

            try
            {
                var result = _dispatcher.Dispatch(uiApp, pending.Tool, pending.Arguments);
                pending.TrySetResult(result);
            }
            catch (Exception ex)
            {
                pending.TrySetException(ex);
            }
        }
    }

    private void ThrowIfDisposed()
    {
        if (_disposed)
        {
            throw new ObjectDisposedException(nameof(BridgeRequestBroker));
        }
    }

    private sealed class PendingBridgeRequest
    {
        private readonly TaskCompletionSource<object?> _tcs = new(TaskCreationOptions.RunContinuationsAsynchronously);

        public PendingBridgeRequest(string tool, JsonElement arguments)
        {
            Tool = tool;
            Arguments = arguments;
        }

        public string Tool { get; }

        public JsonElement Arguments { get; }

        public Task<object?> Task => _tcs.Task;

        public void TrySetException(Exception ex)
        {
            _tcs.TrySetException(ex);
        }

        public void TrySetResult(object? result)
        {
            _tcs.TrySetResult(result);
        }
    }
}
