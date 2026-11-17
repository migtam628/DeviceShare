"""Windows GDI document spooler backend for selected, approved printers.

PDFium renders PDF pages to bounded bitmaps; Pillow handles PNG. The Windows
printer driver receives raster pages through its DC, not raw PDF bytes.
Submission to the spooler does not prove a physical page was printed.
"""
from __future__ import annotations

from io import BytesIO
from typing import Iterator

MAX_PAGES = 12
MAX_PIXELS = 24_000_000


def render_pages(data: bytes, mime_type: str) -> Iterator["Image.Image"]:
    from PIL import Image

    if mime_type == "image/png":
        with Image.open(BytesIO(data)) as loaded:
            if loaded.format != "PNG":
                raise ValueError("Data is not a PNG image")
            if loaded.width * loaded.height > MAX_PIXELS:
                raise ValueError("PNG dimensions exceed the safe page limit")
            loaded.load()
            yield loaded.convert("RGB")
    elif mime_type == "application/pdf":
        import pypdfium2 as pdfium

        with pdfium.PdfDocument(data) as document:
            if not 1 <= len(document) <= MAX_PAGES:
                raise ValueError("PDF documents are limited to 12 nonempty pages")
            for index in range(len(document)):
                page = document[index]
                try:
                    width, height = page.get_size()
                    if width <= 0 or height <= 0 or int(width * 2) * int(height * 2) > MAX_PIXELS:
                        raise ValueError("PDF page dimensions exceed the safe limit")
                    bitmap = page.render(scale=2, fill_color=(255, 255, 255, 255))
                    try:
                        yield bitmap.to_pil().convert("RGB").copy()
                    finally:
                        bitmap.close()
                finally:
                    page.close()
    else:
        raise ValueError("supported document formats: PDF, PNG")


def _fit(image_size: tuple[int, int], printable_size: tuple[int, int]) -> tuple[int, int, int, int]:
    iw, ih = image_size
    pw, ph = printable_size
    if min(iw, ih, pw, ph) <= 0:
        raise ValueError("invalid image or printer page dimensions")
    scale = min(pw / iw, ph / ih)
    width, height = max(1, round(iw * scale)), max(1, round(ih * scale))
    return ((pw - width) // 2, (ph - height) // 2,
            (pw + width) // 2, (ph + height) // 2)


def print_document(printer: str, data: bytes, mime_type: str, options: dict) -> dict[str, str]:
    import win32con
    import win32gui
    import win32print
    import win32ui
    from PIL import ImageWin

    if options.get("tray"):
        raise ValueError("Paper source selection on Windows is not yet supported")
    copies = options.get("copies", 1)
    media = options.get("media", "Letter")
    sides = options.get("sides", "one-sided")
    if type(copies) is not int or not 1 <= copies <= 5:
        raise ValueError("copies must be an integer from 1 to 5")
    if media not in ("Letter", "A4") or sides not in ("one-sided", "two-sided-long-edge"):
        raise ValueError("unsupported paper size or duplex setting")
    if mime_type not in ("application/pdf", "image/png"):
        raise ValueError("unsupported document type")

    # Opening the selected queue returns driver DEVMODE settings. The printer
    # DC will use them for page size and duplex, independent of system defaults.
    handle = win32print.OpenPrinter(printer)
    try:
        mode = win32print.GetPrinter(handle, 2).get("pDevMode")
        if mode is None:
            raise RuntimeError("Printer driver did not provide page settings")
        mode.PaperSize = win32con.DMPAPER_LETTER if media == "Letter" else win32con.DMPAPER_A4
        mode.Duplex = (win32con.DMDUP_SIMPLEX if sides == "one-sided"
                       else win32con.DMDUP_VERTICAL)
        mode.Fields |= win32con.DM_PAPERSIZE | win32con.DM_DUPLEX
        raw_dc = win32gui.CreateDC("WINSPOOL", printer, mode)
    finally:
        win32print.ClosePrinter(handle)

    dc = win32ui.CreateDCFromHandle(raw_dc)
    started = False
    try:
        printable = (dc.GetDeviceCaps(win32con.HORZRES), dc.GetDeviceCaps(win32con.VERTRES))
        if min(printable) <= 0:
            raise RuntimeError("Printer driver returned an invalid printable area")
        job_id = dc.StartDoc("DeviceShare document")
        started = True
        for _ in range(copies):
            for image in render_pages(data, mime_type):
                dc.StartPage()
                ImageWin.Dib(image).draw(dc.GetHandleOutput(), _fit(image.size, printable))
                dc.EndPage()
        dc.EndDoc()
        started = False
        return {"queue": "windows-spooler", "job_id": str(job_id),
                "notice": "Accepted by spooler; verify physical page output"}
    except Exception:
        if started:
            dc.AbortDoc()
        raise
    finally:
        dc.DeleteDC()
