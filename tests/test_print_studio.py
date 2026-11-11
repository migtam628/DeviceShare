import base64
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from reportlab.pdfgen.canvas import Canvas

from deviceshare.hub import create_app
from deviceshare.models import JobCreate
from deviceshare.printing import PrintSubmission, TextSubmission, render_pdf
from deviceshare.backends import _document_print

KEY = "admin-test-key-for-print-studio-12345"
AUTH = {"X-API-Key": KEY}


def test_test_page_and_custom_text_are_valid_pdf():
    sample = PrintSubmission(agent_id="station", device_id="printer:HP_ENVY_6000")
    data = render_pdf(sample, test_page=True)
    assert data.startswith(b"%PDF-")
    assert len(data) < 1024 * 1024
    custom = TextSubmission(agent_id="station", device_id="printer:HP_ENVY_6000",
                            title="Ticket", text="Hello!\nLine 2", media="A4")
    assert render_pdf(custom, test_page=False).startswith(b"%PDF-")


def test_print_requires_online_agent_and_known_printer(tmp_path):
    app = create_app(store_path=str(tmp_path / "print.db"), api_key=KEY)
    with TestClient(app) as client:
        body = {"agent_id": "station", "device_id": "printer:HP_ENVY_6000"}
        response = client.post("/v1/print/test", headers=AUTH, json=body)
        assert response.status_code == 409
        assert client.get("/v1/jobs", headers=AUTH).json() == []


def test_document_print_options_reject_bad_copies():
    with pytest.raises(ValueError):
        JobCreate(agent_id="station", device_id="printer:HP",
                  operation="print_document", data_base64=base64.b64encode(b"%PDF").decode(),
                  options={"mime_type": "application/pdf", "copies": 500})


def test_native_lp_invocation_is_bounded(tmp_path):
    with patch("deviceshare.backends.platform.system", return_value="Darwin"), \
         patch("deviceshare.backends.shutil.which", return_value="/usr/bin/lp"), \
         patch("deviceshare.backends.subprocess.run") as run:
        run.return_value.returncode = 0
        run.return_value.stdout = b"request id is HP-123 (1 file(s))\n"
        _document_print("HP_ENVY_6000", b"%PDF-test", "application/pdf",
                        {"copies": 2, "media": "A4", "sides": "one-sided"})
        args = run.call_args.args[0]
        assert args[:3] == ["lp", "-d", "HP_ENVY_6000"]
        assert "-n" in args and "2" in args
        assert "media=A4" in args and "sides=one-sided" in args
