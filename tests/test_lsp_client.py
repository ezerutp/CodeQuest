import io
import sys
from pathlib import Path

import pytest

from codequest.core.lsp.client import LspClient, LspError, encode_message, read_message
from codequest.core.lsp.models import completion_items

SERVER = Path(__file__).parent / "fixtures" / "fake_lsp_server.py"


def test_messages_round_trip_with_utf8() -> None:
    raw = encode_message({"jsonrpc": "2.0", "method": "x", "params": {"text": "año ñ"}})
    stream = io.BytesIO(raw + raw)
    assert read_message(stream)["params"]["text"] == "año ñ"
    assert read_message(stream) is not None and read_message(stream) is None


def test_request_notifications_and_close(tmp_path: Path) -> None:
    notifications = []
    client = LspClient([sys.executable, str(SERVER), "ok"], cwd=tmp_path,
                       on_notification=lambda method, params: notifications.append((method, params)))
    assert client.request("initialize", {}, timeout=10) == {"capabilities": {}}
    client.notify("initialized", {})
    uri = (tmp_path / "A.java").as_uri()
    client.notify("textDocument/didOpen", {"textDocument": {"uri": uri, "text": "HttpStatus."}})
    result = client.request("textDocument/completion", {"textDocument": {"uri": uri},
                                                         "position": {"line": 0, "character": 11}}, timeout=10)
    assert [item.insert_text for item in completion_items(result)] == ["NO_CONTENT", "OK"]
    assert ("language/status", {"type": "ServiceReady"}) in notifications
    with pytest.raises(LspError, match="no existe"):
        client.request("fail", {}, timeout=10)
    client.close()
    assert not client.is_running
    with pytest.raises(LspError):
        client.request("initialize", {}, timeout=1)


def test_pending_request_fails_when_the_server_dies(tmp_path: Path) -> None:
    client = LspClient([sys.executable, str(SERVER), "crash"], cwd=tmp_path)
    client.request("initialize", {}, timeout=10)
    with pytest.raises(LspError):
        client.request("textDocument/completion", {}, timeout=10)
    client.close()


def test_completion_items_accept_plain_lists_and_skip_garbage() -> None:
    items = completion_items([{"label": "save(S entity) : S", "kind": 2, "filterText": "save"}, {"kind": 2}, "x"])
    assert len(items) == 1 and items[0].insert_text == "save" and items[0].kind == "method"
    assert completion_items(None) == []
