"""Server-side, bounded PDF generation for safe printer test and custom text jobs.

Generated PDFs use reportlab's bundled standard fonts; no external paths,
user-supplied shell commands, remote URLs or arbitrary files are opened.
"""
from __future__ import annotations

from io import BytesIO
from datetime import datetime, timezone
import re
import textwrap

from pydantic import BaseModel, Field
from typing import Literal

MAX_TEXT_CHARACTERS = 12000
MAX_TITLE_CHARACTERS = 80


class PrintSubmission(BaseModel):
    agent_id: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_.-]+$")
    device_id: str = Field(min_length=9, max_length=300, pattern=r"^printer:.+")
    copies: int = Field(default=1, ge=1, le=5)
    media: Literal["Letter", "A4"] = "Letter"
    sides: Literal["one-sided", "two-sided-long-edge"] = "one-sided"


class TextSubmission(PrintSubmission):
    text: str = Field(min_length=1, max_length=MAX_TEXT_CHARACTERS)
    title: str = Field(default="DeviceShare custom print", min_length=1, max_length=MAX_TITLE_CHARACTERS)


def _safe_pdf_text(s: str) -> str:
    # Standard built-in PDF fonts support WinAnsi. Keep characters representable
    # by this encoding; replace control characters with spaces, never commands.
    s = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", " ", s)
    return s.encode("cp1252", errors="replace").decode("cp1252")


def render_pdf(job: PrintSubmission | TextSubmission, *, test_page: bool) -> bytes:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.pdfgen.canvas import Canvas

    output = BytesIO()
    width, height = letter if job.media == "Letter" else A4
    pdf = Canvas(output, pagesize=(width, height), pageCompression=1)
    pdf.setTitle("DeviceShare printer test" if test_page else _safe_pdf_text(job.title))
    margin = 48

    def header(title: str):
        pdf.setFont("Helvetica-Bold", 18)
        pdf.drawString(margin, height - 60, title[:70])
        pdf.setFont("Helvetica", 9)
        pdf.setFillGray(0.40)
        pdf.drawString(margin, height - 77, "DeviceShare • Queued through selected agent")
        pdf.setFillGray(0)
        pdf.line(margin, height - 91, width - margin, height - 91)

    if test_page:
        header("DeviceShare Printer Test")
        y = height - 132
        info = [
            ("Printer", _safe_pdf_text(job.device_id.removeprefix("printer:"))[:65]),
            ("Agent", job.agent_id),
            ("Paper", job.media),
            ("Copies", str(job.copies)),
            ("Date (UTC)", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")),
        ]
        for label, value in info:
            pdf.setFont("Helvetica-Bold", 11)
            pdf.drawString(margin, y, label + ":")
            pdf.setFont("Helvetica", 11)
            pdf.drawString(margin + 108, y, value)
            y -= 27
        pdf.setFont("Helvetica-Bold", 13)
        pdf.drawString(margin, y - 19, "Print quality check")
        y -= 50
        segment_width = (width - 2 * margin) / 6
        for i in range(6):
            gray = i / 5
            pdf.setFillGray(gray)
            pdf.rect(margin + i * segment_width, y - 27, segment_width, 27, fill=1, stroke=0)
        pdf.setFillGray(0)
        y -= 55
        pdf.setFont("Helvetica", 12)
        pdf.drawString(margin, y, "ABCDEFGHIJKLMNOPQRSTUVWXYZ  0123456789")
        pdf.setFont("Helvetica", 10)
        pdf.drawString(margin, y - 21, "abcdefghijklmnopqrstuvwxyz  !@#$%&*()-+=/?")
        pdf.setFont("Helvetica", 9)
        pdf.drawString(margin, y - 58, "If this page is physically printed correctly, mark the test successful.")
        pdf.setStrokeGray(0.5)
        pdf.rect(margin, 45, width - 2 * margin, height - 90, fill=0, stroke=1)
    else:
        header(_safe_pdf_text(job.title))
        pdf.setFont("Helvetica", 10)
        y = height - 130
        line_height = 14
        pages = 1
        for paragraph in job.text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            paragraph = _safe_pdf_text(paragraph).expandtabs(4)
            # Hard wrap to fit a normal one-column printed page.
            lines = textwrap.wrap(paragraph, width=95, break_long_words=True,
                                  break_on_hyphens=False, replace_whitespace=False,
                                  drop_whitespace=False) or [""]
            for line in lines:
                if y < 58:
                    pdf.showPage()
                    pages += 1
                    if pages > 12:
                        raise ValueError("Custom text document is limited to 12 pages")
                    header(_safe_pdf_text(job.title) + f" (page {pages})")
                    pdf.setFont("Helvetica", 10)
                    y = height - 130
                pdf.drawString(margin, y, line)
                y -= line_height
        if not job.text.strip():
            raise ValueError("Custom print text must not be blank")

    pdf.showPage()
    pdf.save()
    data = output.getvalue()
    if len(data) > 1024 * 1024:
        raise ValueError("Generated PDF exceeds print payload limit")
    return data
