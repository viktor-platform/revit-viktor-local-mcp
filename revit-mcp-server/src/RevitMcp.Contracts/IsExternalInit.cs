// Polyfill for C# 9 records in netstandard2.0
// This type is required for init-only properties to work
namespace System.Runtime.CompilerServices;

internal static class IsExternalInit
{
}
