"""Servidor LSP falso para los tests: responde como jdtls a lo mínimo que usa CodeQuest.

Modos (primer argumento): "ok" (normal), "crash" (se cierra tras initialize), "silent" (nunca está listo).
Escribe en stdout solo mensajes LSP; lo recibido se anota en el archivo del segundo argumento.
"""

import json
import sys

MODE = sys.argv[1] if len(sys.argv) > 1 else "ok"
RECEIVED = open(sys.argv[2], "a", encoding="utf-8") if len(sys.argv) > 2 else None  # noqa: SIM115


def read():
    length = None
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        if not line.strip():
            break
        name, _, value = line.decode().partition(":")
        if name.lower() == "content-length":
            length = int(value)
    return json.loads(sys.stdin.buffer.read(length))


def send(message):
    body = json.dumps(message).encode()
    sys.stdout.buffer.write(f"Content-Length: {len(body)}\r\n\r\n".encode() + body)
    sys.stdout.buffer.flush()


documents = {}
while (message := read()) is not None:
    method = message.get("method")
    if RECEIVED is not None:
        RECEIVED.write(json.dumps(message) + "\n")
        RECEIVED.flush()
    if method == "initialize":
        send({"jsonrpc": "2.0", "id": message["id"], "result": {"capabilities": {}}})
        if MODE == "crash":
            sys.exit(1)
    elif method == "initialized" and MODE == "ok":
        send({"jsonrpc": "2.0", "method": "language/status", "params": {"type": "Starting", "message": "Importing"}})
        send({"jsonrpc": "2.0", "id": 99, "method": "client/registerCapability", "params": {}})
        send({"jsonrpc": "2.0", "method": "language/status", "params": {"type": "ServiceReady"}})
    elif method == "textDocument/didOpen":
        documents[message["params"]["textDocument"]["uri"]] = message["params"]["textDocument"]["text"]
    elif method == "textDocument/didChange":
        documents[message["params"]["textDocument"]["uri"]] = message["params"]["contentChanges"][0]["text"]
    elif method == "textDocument/completion":
        uri = message["params"]["textDocument"]["uri"]
        position = message["params"]["position"]
        line = documents.get(uri, "").split("\n")[position["line"]][:position["character"]]
        items = []
        if line.endswith("HttpStatus."):
            items = [{"label": "NO_CONTENT : HttpStatus", "kind": 20, "insertText": "NO_CONTENT"},
                     {"label": "OK : HttpStatus", "kind": 20, "textEdit": {"newText": "OK"}}]
        send({"jsonrpc": "2.0", "id": message["id"], "result": {"isIncomplete": False, "items": items}})
    elif method == "fail":
        send({"jsonrpc": "2.0", "id": message["id"], "error": {"code": -32601, "message": "no existe"}})
    elif method == "shutdown":
        send({"jsonrpc": "2.0", "id": message["id"], "result": None})
    elif method == "exit":
        break
