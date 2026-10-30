using System;
using System.Windows;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using Point = System.Windows.Point;
using Pen = System.Windows.Media.Pen;
using Color = System.Windows.Media.Color;

namespace RevitMcp.RevitAddin.Bridge;

internal static class AdapterRibbonIcons
{
    public static BitmapSource Running(int size) => Render(size, drawing =>
    {
        drawing.DrawEllipse(Brush(22, 54, 82), null, new Point(16, 16), 15, 15);
        drawing.DrawGeometry(
            Brush(255, 198, 55),
            null,
            Geometry.Parse("M 18,3 L 9,17 L 15,17 L 12,29 L 24,13 L 17,13 Z"));
    });

    public static BitmapSource Stopped(int size) => Render(size, drawing =>
    {
        drawing.DrawEllipse(
            Brush(240, 245, 247),
            new Pen(Brush(65, 92, 105), 2),
            new Point(16, 16),
            14,
            14);
        drawing.DrawGeometry(
            Brush(25, 141, 105),
            null,
            Geometry.Parse("M 12,8 L 24,16 L 12,24 Z"));
    });

    public static BitmapSource Port(int size) => Render(size, drawing =>
    {
        drawing.DrawRoundedRectangle(Brush(38, 116, 176), null, new Rect(1, 1, 30, 30), 6, 6);
        var pen = new Pen(Brush(255, 255, 255), 2.4);
        drawing.DrawLine(pen, new Point(7, 18), new Point(25, 18));
        drawing.DrawEllipse(Brush(255, 255, 255), null, new Point(9, 18), 4, 4);
        drawing.DrawEllipse(Brush(255, 255, 255), null, new Point(23, 18), 4, 4);
        drawing.DrawLine(pen, new Point(16, 8), new Point(16, 14));
    });

    private static BitmapSource Render(int size, Action<DrawingContext> draw)
    {
        var visual = new DrawingVisual();
        using (var context = visual.RenderOpen())
        {
            context.PushTransform(new ScaleTransform(size / 32.0, size / 32.0));
            draw(context);
            context.Pop();
        }

        var bitmap = new RenderTargetBitmap(size, size, 96, 96, PixelFormats.Pbgra32);
        bitmap.Render(visual);
        bitmap.Freeze();
        return bitmap;
    }

    private static SolidColorBrush Brush(byte red, byte green, byte blue)
    {
        var brush = new SolidColorBrush(Color.FromRgb(red, green, blue));
        brush.Freeze();
        return brush;
    }
}
