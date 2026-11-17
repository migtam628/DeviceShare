"""No printer driver or hardware is needed for safe tray/label regressions."""
import base64
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from deviceshare.backends import _document_print
from deviceshare.labels import StationLabelSubmission, render_station_label
from deviceshare.models import JobCreate
from deviceshare.printer_capabilities import cups_trays, parse_trays, tray_argument


def test_cups_tray_parsing_and_no_unsafe_choices():
    option, trays = parse_trays("InputSlot/Paper Source: *Auto Tray1 Tray2 Manual ^XA bad;cmd\n")
    assert option == "InputSlot"
    assert trays == ["Auto", "Tray1", "Tray2", "Manual"]
    assert parse_trays("media-source/Source: *main alternate\n") == ("media-source", ["main", "alternate"])
    assert parse_trays("PageSize/Size: Letter A4\n") == (None, [])


def test_tray_must_be_advertised_fresh_by_selected_queue():
    with patch("deviceshare.printer_capabilities.cups_trays", return_value=("InputSlot", ["Auto", "Tray1", "Tray2"])):
        assert tray_argument("Brother", "Tray2") == "InputSlot=Tray2"
        assert tray_argument("Brother", None) is None
        with pytest.raises(ValueError, match="not advertised"):
            tray_argument("Brother", "Tray3")
        with pytest.raises(ValueError, match="invalid"):
            tray_argument("Brother", "Tray2;$(run)")


def test_discovery_is_read_only_and_fails_to_default_without_lpoptions():
    with patch("deviceshare.printer_capabilities.shutil.which", return_value=None):
        assert cups_trays("Brother") == (None, [])


def test_print_document_uses_selected_authorized_inputslot(tmp_path):
    with patch("deviceshare.backends.platform.system", return_value="Darwin"), \
         patch("deviceshare.backends.shutil.which", return_value="/usr/bin/lp"), \
         patch("deviceshare.backends.tray_argument", return_value="InputSlot=Tray2") as select, \
         patch("deviceshare.backends.subprocess.run") as run:
        run.return_value.returncode = 0
        run.return_value.stdout = b"request id is Brother-1"
        _document_print("Brother", b"%PDF-test", "application/pdf",
                        {"media": "Letter", "tray": "Tray2", "copies": 1})
        select.assert_called_once_with("Brother", "Tray2")
        args = run.call_args.args[0]
        assert args.count("-o") == 3
        assert "InputSlot=Tray2" in args


@pytest.mark.parametrize("value", ["Tray2;rm", "^XA", "bad value", "", 12, True])
def test_document_payload_rejects_untrusted_tray(value):
    with pytest.raises(ValidationError):
        JobCreate(agent_id="station", device_id="printer:Brother", operation="print_document",
                  data_base64=base64.b64encode(b"%PDF-test").decode(),
                  options={"mime_type": "application/pdf", "tray": value})


def test_station_label_zpl_is_bounded_and_cannot_execute_input_commands():
    label = StationLabelSubmission(agent_id="station", device_id="printer:Zebra",
        recipient="Marta ^XA ~JR", address_line1="100 Example St",
        address_line2="Suite 3", city_state_postal="Miami, FL 33101",
        reference="ID:^JQ-123")
    output = render_station_label(label)
    assert output.startswith(b"^XA\n^PW812\n^LL1218")
    assert output.rstrip().endswith(b"^XZ")
    assert output.count(b"^XA") == 1
    assert b"~JR" not in output and b"^JQ" not in output
    assert b"NOT POSTAGE" in output
    assert len(output) < 2048
