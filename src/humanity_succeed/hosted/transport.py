"""Original transport implementation. No retries, proxies, redirects or discovery."""

from __future__ import annotations

import http.client
import multiprocessing
import re
import socket
import ssl
import time
from dataclasses import dataclass
from typing import Any

from ..canonical import canonical_bytes, strict_json_loads
from .contracts import Settings


class HostedFailure(RuntimeError):
    def __init__(self, code: str, *, attempted: bool = False, elapsed_ms: int = 0, unknown: bool = False):
        super().__init__(code)  # Never include remote error text or credentials.
        self.code = code
        self.record = {
            "schema_id": "hs-hosted-failure/1",
            "attempted": attempted,
            "elapsed_ms": elapsed_ms,
            "completion_unknown": unknown,
            "billing_unknown": attempted,
        }


def encode(observation: bytes, model: str, settings: Settings) -> bytes:
    doc = strict_json_loads(observation)
    if set(doc) != {"interface", "messages"} or doc["interface"] != "hs-workroom-interface/1":
        raise HostedFailure("invalid_observation")
    messages = []
    for index, message in enumerate(doc["messages"]):
        if set(message) != {"role", "content"} or not isinstance(message["content"], str):
            raise HostedFailure("invalid_observation")
        role = message["role"]
        expected = (
            "system" if index == 0 else "user" if index == 1 else "assistant" if index % 2 == 0 else "tool"
        )
        if role != expected:
            raise HostedFailure("invalid_observation_order")
        if role == "tool":
            # Tagged envelope, not a fabricated native tool call. Exact content is reversible.
            messages.append(
                {
                    "role": "user",
                    "content": canonical_bytes(
                        {
                            "encoding": "hs-deepseek-transcript/1",
                            "original_role": "tool",
                            "content": message["content"],
                        }
                    ).decode(),
                }
            )
        elif role in ("system", "user", "assistant"):
            messages.append(dict(message))
        else:
            raise HostedFailure("invalid_observation")
    return canonical_bytes(
        {
            "model": model,
            "messages": messages,
            "stream": False,
            "response_format": {"type": "json_object"},
            "thinking": {"type": settings.thinking},
            "reasoning_effort": settings.reasoning_effort,
            "max_tokens": settings.max_tokens,
        }
    )


def decode(request: bytes) -> bytes:
    doc = strict_json_loads(request)
    messages = []
    for index, m in enumerate(doc["messages"]):
        # Internal transcript starts with system+user and thereafter alternates assistant+tool.
        if index >= 2 and index % 2 == 1:
            wrapped = strict_json_loads(m["content"])
            if (
                m["role"] != "user"
                or set(wrapped) != {"encoding", "original_role", "content"}
                or wrapped["encoding"] != "hs-deepseek-transcript/1"
                or wrapped["original_role"] != "tool"
            ):
                raise HostedFailure("invalid_encoding")
            messages.append({"role": "tool", "content": wrapped["content"]})
        else:
            messages.append(m)
    return canonical_bytes({"interface": "hs-workroom-interface/1", "messages": messages})


@dataclass(frozen=True)
class FakeReply:
    status: int = 200
    body: bytes = b""
    error: str | None = None
    delay_seconds: float = 0


def _https(body: bytes, secret: str, timeout: float, size: int) -> tuple[int, bytes]:
    connection = http.client.HTTPSConnection(
        "api.deepseek.com", timeout=timeout, context=ssl.create_default_context()
    )
    try:
        connection.request(
            "POST",
            "/chat/completions",
            body=body,
            headers={"Authorization": "Bearer " + secret, "Content-Type": "application/json"},
        )
        response = connection.getresponse()
        data = response.read(size + 1) if response.status == 200 else b""
        return response.status, data
    finally:
        connection.close()


def _contains_secret(value: Any, secret: str) -> bool:
    if isinstance(value, str):
        for _ in range(4):
            if secret in value:
                return True
            value = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m[1], 16)), value)
        return secret in value
    if isinstance(value, list):
        return any(_contains_secret(v, secret) for v in value)
    if isinstance(value, dict):
        return any(_contains_secret(k, secret) or _contains_secret(v, secret) for k, v in value.items())
    return False


def _worker(pipe, request: bytes, secret: str, timeout: float, size: int, fake: FakeReply | None) -> None:
    """Worker receives serialized observations/config only; no case/store/evaluator handles."""
    start = time.monotonic()
    try:
        if fake is not None:

            def denied(*args, **kwargs):
                raise RuntimeError("network_denied_in_simulation")

            socket.socket.connect = denied  # type: ignore[method-assign]
            socket.create_connection = denied
            if fake.delay_seconds:
                time.sleep(fake.delay_seconds)
            if fake.error:
                code = (
                    fake.error
                    if fake.error in ("timeout", "tls_error", "transport_error")
                    else "fake_transport_error"
                )
                raise HostedFailure(code, attempted=True, unknown=code == "timeout")
            status, data = fake.status, fake.body
        else:
            status, data = _https(request, secret, timeout, size)
        codes = {
            401: "authentication_error",
            402: "balance_error",
            422: "request_rejected",
            429: "rate_limited",
            500: "server_error",
            503: "server_unavailable",
        }
        if status != 200:
            raise HostedFailure(
                codes.get(status, "redirect_refused" if 300 <= status < 400 else "http_error"), attempted=True
            )
        if len(data) > size:
            raise HostedFailure("response_size_limit", attempted=True, unknown=True)
        try:
            parsed_echo = _contains_secret(strict_json_loads(data), secret)
        except Exception:
            parsed_echo = False
        if secret.encode() in data or parsed_echo:
            raise HostedFailure("credential_echo", attempted=True)
        pipe.send((True, data, round((time.monotonic() - start) * 1000)))
    except HostedFailure as failure:
        pipe.send((False, failure.code, round((time.monotonic() - start) * 1000)))
    except TimeoutError:
        pipe.send((False, "timeout", round((time.monotonic() - start) * 1000)))
    except ssl.SSLError:
        pipe.send((False, "tls_error", round((time.monotonic() - start) * 1000)))
    except Exception:
        pipe.send((False, "transport_error", round((time.monotonic() - start) * 1000)))
    finally:
        pipe.close()


def dispatch(
    request: bytes, secret: str, timeout: float, size: int, fake: FakeReply | None
) -> tuple[bytes, int]:
    ctx = multiprocessing.get_context("spawn")
    receiver, sender = ctx.Pipe(duplex=False)
    process = ctx.Process(target=_worker, args=(sender, request, secret, timeout, size, fake))
    start = time.monotonic()
    process.start()
    sender.close()
    try:
        remaining = timeout - (time.monotonic() - start)
        if remaining <= 0 or not receiver.poll(remaining):
            raise HostedFailure(
                "timeout", attempted=True, elapsed_ms=round((time.monotonic() - start) * 1000), unknown=True
            )
        try:
            ok, value, elapsed = receiver.recv()
        except EOFError:
            raise HostedFailure("worker_failure", attempted=True, unknown=True) from None
        if not ok:
            raise HostedFailure(
                value, attempted=True, elapsed_ms=elapsed, unknown=value in ("timeout", "response_size_limit")
            )
        return value, round((time.monotonic() - start) * 1000)
    finally:
        if process.is_alive():
            process.terminate()
        process.join()
        receiver.close()


def unpack(data: bytes, elapsed: int, allowed: list[str], action_limit: int) -> tuple[str, dict[str, Any]]:
    try:
        doc = strict_json_loads(data)
        choices = doc["choices"]
        if len(choices) != 1 or choices[0]["index"] != 0:
            raise ValueError
        choice = choices[0]
        message = choice["message"]
        content = message["content"]
        if content is None:
            content = ""
        if not isinstance(content, str) or message["role"] != "assistant" or doc["model"] not in allowed:
            raise ValueError
        finish = choice["finish_reason"]
        if finish not in (
            "stop",
            "length",
            "content_filter",
            "tool_calls",
            "insufficient_system_resource",
            "aborted",
        ):
            raise ValueError
        from ..canonical import sha256_bytes

        metadata = {
            "schema_id": "hs-hosted-response/1",
            "response_sha256": sha256_bytes(data),
            "returned_model": doc["model"],
            "response_id": doc.get("id"),
            "system_fingerprint": doc.get("system_fingerprint"),
            "usage": doc.get("usage"),
            "finish_reason": finish,
            "elapsed_ms": elapsed,
            "execute_content": finish == "stop",
        }
        from .contracts import ResponseRecord

        ResponseRecord.model_validate(metadata, strict=True)
        return content, metadata
    except HostedFailure:
        raise
    except Exception:
        raise HostedFailure("api_protocol_error", attempted=True, elapsed_ms=elapsed) from None
