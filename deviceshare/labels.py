"""Bounded, plain-text 4 x 6 inch ZPL station labels (not carrier postage)."""
from __future__ import annotations

import re
import unicodedata

from pydantic import BaseModel, Field, field_validator

class StationLabelSubmission(BaseModel):
    agent_id: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_.-]+$")
    device_id: str = Field(min_length=9, max_length=300, pattern=r"^printer:.+")
    recipient: str = Field(min_length=1, max_length=70)
    address_line1: str = Field(min_length=1, max_length=80)
    address_line2: str = Field(default="", max_length=80)
    city_state_postal: str = Field(min_length=1, max_length=90)
    reference: str = Field(min_length=1, max_length=64)

    @field_validator("recipient", "address_line1", "city_state_postal", "reference")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("label fields cannot be blank")
        return value


def _zpl_text(value: str, limit: int) -> str:
    # Restrict Zebra control characters and normalize Unicode to a printable
    # 203-dpi US-ASCII text label. Never pass direct ZPL from form fields.
    text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^\x20-\x5d\x5f-\x7d]", " ", text).strip()[:limit]


def render_station_label(label: StationLabelSubmission) -> bytes:
    """203-dpi 4x6 ZPL: identifying label only, *not* paid carrier shipping."""
    fields = [
        ("STATION LABEL - NOT POSTAGE", 35, 42, 32),
        ("SHIP TO", 35, 162, 30),
        (_zpl_text(label.recipient, 36), 35, 214, 45),
        (_zpl_text(label.address_line1, 40), 35, 292, 34),
        (_zpl_text(label.address_line2, 40), 35, 348, 34),
        (_zpl_text(label.city_state_postal, 40), 35, 406, 34),
        ("REFERENCE", 35, 548, 30),
        (_zpl_text(label.reference, 40), 35, 601, 44),
    ]
    commands = ["^XA", "^PW812", "^LL1218", "^LH0,0", "^FO24,111^GB760,3,3^FS"]
    for value, x, y, size in fields:
        if value:
            commands.append(f"^FO{x},{y}^A0N,{size},{size}^FD{value}^FS")
    commands.extend(["^FO24,720^GB760,3,3^FS",
                     "^FO35,753^A0N,26,26^FDConfirm physical output before marking complete^FS",
                     "^XZ"])
    return ("\n".join(commands) + "\n").encode("ascii")
