"""Supported Codex app-server client. Uses connected apps, never OAuth secrets.

An ephemeral thread holds MCP connections only. No model turn is started.
"""
from __future__ import annotations

import atexit
import json
import re
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path


ALLOWED_TOOLS = {
    "gmail.get_profile", "gmail.search_email_ids", "gmail.read_email", "gmail.batch_read_email",
    "gmail.create_draft", "gmail.send_email", "gmail.read_attachment",
    "google_drive.get_profile", "google_drive.search", "google_drive.fetch",
    "google_drive.get_file_metadata", "google_drive.create_folder", "google_drive.upload_file",
    "search_service.web_run",
}


class ConnectorError(RuntimeError):
    def __init__(self, message):
        message = re.sub(r'https?://[^\s"<>]+', lambda match: '[private file reference]' if re.search(r'[?&](?:sig|token|signature)=', match[0], re.I) else match[0], str(message))
        super().__init__(message)


def unpack(result: dict) -> dict:
    if result.get("isError"):
        message = " ".join(c.get("text", "") for c in result.get("content", []) if c.get("type") == "text")
        raise ConnectorError(message[:1000] or "Connected app reported an error")
    data = result.get("structuredContent")
    if data is not None:
        return data
    for block in result.get("content", []):
        if block.get("type") == "text":
            try:
                data = json.loads(block["text"])
                if isinstance(data, dict):
                    return data
            except (ValueError, KeyError):
                pass
    return {"text": "\n".join(c.get("text", "") for c in result.get("content", []) if c.get("type") == "text")}


class ConnectorBridge:
    def __init__(self, workspace: Path, timeout: float = 180):
        self.workspace = workspace.resolve()
        self.timeout = timeout
        self.proc = None
        self.thread_id = None
        self.tools = {}
        self.installed = []
        self.pending = {}
        self.approvals = {}
        self.lock = threading.RLock()
        self.write_lock = threading.Lock()
        self.start_lock = threading.Lock()
        self.sequence = 0
        atexit.register(self.close)

    def _send(self, value):
        with self.write_lock:
            if not self.proc or self.proc.poll() is not None:
                raise ConnectorError("Codex connector process has stopped. Reconnect in Connections.")
            self.proc.stdin.write(json.dumps(value) + "\n")
            self.proc.stdin.flush()

    def _read(self, process):
        try:
            for line in process.stdout:
                try:
                    value = json.loads(line)
                except ValueError:
                    continue
                if "id" in value and ("result" in value or "error" in value):
                    with self.lock:
                        request = self.pending.get(value["id"])
                    if request:
                        request["response"] = value
                        request["event"].set()
                elif "id" in value and "method" in value:
                    if value["method"] in {"mcpServer/elicitation/request", "tool/requestUserInput"}:
                        approval_id = uuid.uuid4().hex
                        with self.lock:
                            self.approvals[approval_id] = {"id": approval_id, "request_id": value["id"],
                                "method": value["method"], "params": value.get("params", {}), "created": time.time()}
                    else:
                        self._send({"id": value["id"], "error": {"code": -32601, "message": "Unsupported client request"}})
        finally:
            with self.lock:
                for request in self.pending.values():
                    request.setdefault("response", {"error": {"message": "Connector process disconnected"}})
                    request["event"].set()

    def request(self, method, params):
        with self.lock:
            self.sequence += 1
            request_id = self.sequence
            request = {"event": threading.Event()}
            self.pending[request_id] = request
        try:
            self._send({"id": request_id, "method": method, "params": params})
            if not request["event"].wait(self.timeout):
                raise ConnectorError("Connector request timed out. Check Activity before retrying a write.")
            response = request["response"]
            if "error" in response:
                raise ConnectorError(response["error"].get("message", "Connector request failed")[:1000])
            return response["result"]
        finally:
            with self.lock:
                self.pending.pop(request_id, None)

    def start(self):
        with self.start_lock:
            if self.proc and self.proc.poll() is None and self.thread_id:
                return
            binary = shutil.which("codex")
            if not binary:
                candidate = Path.home() / ".local/bin/codex"
                if candidate.is_file():
                    binary = str(candidate)
            if not binary:
                raise ConnectorError("Install Codex CLI and sign in with the same ChatGPT account, then reconnect.")
            self.proc = subprocess.Popen([binary, "app-server", "--listen", "stdio://"], cwd=self.workspace,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, encoding="utf-8", bufsize=1)
            threading.Thread(target=self._read, args=(self.proc,), daemon=True).start()
            try:
                self.request("initialize", {"clientInfo": {"name": "job_agent_workspace", "title": "Job Agent", "version": "0.2.0"},
                    "capabilities": {"experimentalApi": True, "mcpServerOpenaiFormElicitation": True}})
                self._send({"method": "initialized", "params": {}})
                self.installed = self.request("app/installed", {"forceRefresh": True}).get("apps", [])
                thread = self.request("thread/start", {"cwd": str(self.workspace), "ephemeral": True,
                    "sandbox": "read-only", "approvalPolicy": "on-request"})
                self.thread_id = thread["thread"]["id"]
                cursor = None
                self.tools = {}
                while True:
                    inventory = self.request("mcpServerStatus/list", {"threadId": self.thread_id,
                        "detail": "toolsAndAuthOnly", "limit": 100, "cursor": cursor})
                    for server in inventory.get("data", []):
                        for name, spec in server.get("tools", {}).items():
                            if name in ALLOWED_TOOLS:
                                self.tools[name] = {"server": server["name"], "schema": spec.get("inputSchema", {})}
                    cursor = inventory.get("nextCursor")
                    if not cursor:
                        break
            except Exception:
                self.close()
                raise

    def call(self, tool: str, arguments: dict | None = None) -> dict:
        if tool not in ALLOWED_TOOLS:
            raise ConnectorError("This app does not permit that connector action")
        self.start()
        if tool not in self.tools:
            raise ConnectorError(f"{tool.split('.')[0]} is unavailable. Connect its plugin in Codex, then reconnect.")
        result = self.request("mcpServer/tool/call", {"threadId": self.thread_id,
            "server": self.tools[tool]["server"], "tool": tool, "arguments": arguments or {}})
        return unpack(result)

    def pending_approvals(self):
        with self.lock:
            return [{k: v for k, v in item.items() if k != "request_id"} for item in self.approvals.values()]

    def answer_approval(self, approval_id, action, content=None):
        if action not in {"accept", "decline", "cancel"}:
            raise ValueError("Unknown approval action")
        with self.lock:
            item = self.approvals.pop(approval_id, None)
        if not item:
            raise ValueError("Approval has expired")
        if item["method"] == "tool/requestUserInput":
            result = {"answers": content or {}}
        else:
            if item["params"].get("mode") == "openai/userVerification" and action == "accept":
                raise ValueError("This action requires approval in the native Codex app")
            result = {"action": action, "content": content if action == "accept" else None}
        self._send({"id": item["request_id"], "result": result})

    def close(self):
        process = self.proc
        self.thread_id = None
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()

