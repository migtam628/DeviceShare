"""PDF/PNG rendering is testable without reaching a Windows print spooler."""
from io import BytesIO
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image
from reportlab.pdfgen.canvas import Canvas

from deviceshare.windows_print import _fit, render_pages, print_document


def _pdf(pages=2):
    output = BytesIO()
    canvas = Canvas(output, pagesize=(612, 792))
    for index in range(pages):
        canvas.drawString(50, 730, f"Page {index + 1}")
        canvas.showPage()
    canvas.save()
    return output.getvalue()


def test_pdfium_rendering_multiple_pages_to_rgb_bitmaps():
    images = list(render_pages(_pdf(), "application/pdf"))
    assert len(images) == 2
    assert all(p.mode == "RGB" and p.width == 1224 and p.height == 1584 for p in images)


def test_pdfium_rejects_page_count_over_limit():
    with pytest.raises(ValueError, match="12"):
        list(render_pages(_pdf(pages=13), "application/pdf"))


def test_png_rendering_includes_only_one_page():
    stream = BytesIO()
    Image.new("RGBA", (100, 150), (15, 20, 30, 255)).save(stream, format="PNG")
    images = list(render_pages(stream.getvalue(), "image/png"))
    assert len(images) == 1
    assert images[0].mode == "RGB" and images[0].size == (100, 150)


def test_windows_page_fit_centers_without_distortion():
    assert _fit((100, 200), (600, 600)) == (150, 0, 450, 600)
    with pytest.raises(ValueError):
        _fit((0, 20), (600, 600))


@pytest.mark.skipif(sys.platform != "win32", reason="Win32 native driver API test")
def test_windows_document_spools_two_pages_with_explicit_devmode():
    import win32con
    import win32print
    import win32gui
    import win32ui

    mode = SimpleNamespace(PaperSize=0, Duplex=0, Fields=0)
    dc = MagicMock()
    dc.GetDeviceCaps.side_effect = [1000, 1400]
    dc.StartDoc.return_value = 142
    with patch.object(win32print, "OpenPrinter", return_value=44), \
         patch.object(win32print, "GetPrinter", return_value={"pDevMode": mode}), \
         patch.object(win32print, "ClosePrinter"), \
         patch.object(win32gui, "CreateDC", return_value=123), \
         patch.object(win32ui, "CreateDCFromHandle", return_value=dc), \
         patch("PIL.ImageWin.Dib") as dib:
        result = print_document("Brother", _pdf(1), "application/pdf",
                                {"media": "A4", "sides": "two-sided-long-edge", "copies": 2})
    assert result["queue"] == "windows-spooler" and result["job_id"] == "142"
    assert mode.PaperSize == win32con.DMPAPER_A4
    assert mode.Duplex == win32con.DMDUP_VERTICAL
    assert dc.StartPage.call_count == 2 and dc.EndPage.call_count == 2
    assert dib.return_value.draw.call_count == 2
    dc.EndDoc.assert_called_once()
    dc.DeleteDC.assert_called_once()
