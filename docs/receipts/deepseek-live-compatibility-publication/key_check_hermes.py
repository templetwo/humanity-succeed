"""One authorized metadata request. No inference, credential discovery, retry or response text log."""

import argparse
import datetime
import hashlib
import http.client
import json
import os
import re
import signal
import ssl
import stat
import time
from pathlib import Path

from humanity_succeed.canonical import canonical_bytes, load_document, sha256_obj
from humanity_succeed.hosted.provider import implementation_identity
from humanity_succeed.hosted.transport import HostedFailure, _contains_secret


def deadline(*_):
    raise TimeoutError


def read_hermes_deepseek(path):
    # Only the explicitly selected dotenv file and one literal target variable. Never source it.
    try:
        metadata = path.lstat()
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid()
                or stat.S_IMODE(metadata.st_mode) & 0o077 or metadata.st_size > 65536):
            raise ValueError
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as stream:
            data = stream.read(65537)
        if len(data) > 65536:
            raise ValueError
        values = []
        for line in data.splitlines():
            match = re.match(rb"^[ \t]*(?:export[ \t]+)?DEEPSEEK_API_KEY[ \t]*=[ \t]*(.*)$", line)
            if match is not None:
                value = match[1].strip()
                if len(value) >= 2 and value[:1] in (b"'", b'"') and value[-1:] == value[:1]:
                    value = value[1:-1]
                if re.fullmatch(rb"[A-Za-z0-9_-]{8,256}", value) is None:
                    raise ValueError
                values.append(value)
        if not values:
            raise HostedFailure("deepseek_key_not_present")
        if len(values) != 1:
            raise ValueError
        return values[0].decode("ascii")
    except HostedFailure:
        raise
    except Exception:
        raise HostedFailure("credential_file_invalid") from None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--plan-sha256", required=True)
    args = parser.parse_args()
    plan = load_document(args.plan)
    assert sha256_obj(plan) == args.plan_sha256, "key-check scope changed"
    assert implementation_identity() == plan["source"], "pinned implementation changed"
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == plan["probe_sha256"]
    assert plan["endpoint"] == "https://api.deepseek.com/models"
    assert plan["method"] == "GET"
    assert plan["authenticated_metadata_requests"] == 1 and plan["inference_requests"] == 0
    output = Path(plan["output"])
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    output.mkdir(mode=0o700)  # Fresh single-use attempt directory. Never resume or reset it.
    report = {
        "schema_id": "hs-key-connectivity-check/1",
        "scope": "User-requested key check only; not a subject-model run or inference approval",
        "plan_sha256": args.plan_sha256,
        "started_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "source": implementation_identity(),
        "endpoint": plan["endpoint"], "method": "GET",
        "authenticated_metadata_attempts": 0, "inference_requests": 0,
        "credential_read": False, "http_status": None,
        "response_body_retained": False, "usage": None,
        "status": "started_not_completed", "completion_unknown": False,
    }
    reservation = output / "reservation.json"
    reservation.write_bytes(canonical_bytes(report))
    reservation.chmod(0o600)
    started = time.monotonic()
    signal.signal(signal.SIGALRM, deadline)
    signal.setitimer(signal.ITIMER_REAL, plan["whole_request_seconds"])
    connection = None
    try:
        credential = Path(plan["credential_file"])
        if not credential.exists():
            report["status"] = "credential_file_missing"
        else:
            secret = read_hermes_deepseek(credential)
            report["credential_read"] = True
            connection = http.client.HTTPSConnection(
                "api.deepseek.com", timeout=plan["whole_request_seconds"],
                context=ssl.create_default_context(),
            )
            report["authenticated_metadata_attempts"] = 1
            reservation.write_bytes(canonical_bytes(report))
            connection.request("GET", "/models", headers={
                "Authorization": "Bearer " + secret, "Accept": "application/json",
            })
            response = connection.getresponse()
            report["http_status"] = response.status
            body = response.read(plan["response_bytes"] + 1)
            if len(body) > plan["response_bytes"]:
                report["status"] = "response_size_limit"
            elif secret.encode() in body or _contains_secret(body.decode("utf-8", "replace"), secret):
                report["status"] = "credential_echo_discarded"
            elif response.status != 200:
                report["status"] = {
                    401: "authentication_rejected", 403: "access_denied", 402: "balance_error",
                    429: "rate_limited",
                }.get(response.status, "http_error")
            else:
                doc = json.loads(body)
                if _contains_secret(doc, secret):
                    report["status"] = "credential_echo_discarded"
                elif (not isinstance(doc, dict) or doc.get("object") != "list"
                      or not isinstance(doc.get("data"), list)):
                    report["status"] = "invalid_metadata_response"
                else:
                    report["status"] = "authenticated_metadata_request_succeeded"
                    report["model_count"] = len(doc["data"])
                    # Report only documented public identifiers, never arbitrary remote strings.
                    report["deepseek_flash_listed"] = any(
                        isinstance(row, dict) and row.get("id") == "deepseek-flash"
                        for row in doc["data"]
                    )
    except HostedFailure as failure:
        report["status"] = failure.code
    except TimeoutError:
        report["status"] = "timeout"
        report["completion_unknown"] = report["authenticated_metadata_attempts"] == 1
    except ssl.SSLError:
        report["status"] = "tls_failure"
    except (json.JSONDecodeError, UnicodeDecodeError):
        report["status"] = "invalid_metadata_response"
    except KeyboardInterrupt:
        report["status"] = "operator_interrupted"
        report["completion_unknown"] = report["authenticated_metadata_attempts"] == 1
    except Exception:
        report["status"] = "connection_or_local_failure"
        report["completion_unknown"] = report["authenticated_metadata_attempts"] == 1
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        if connection is not None:
            connection.close()
        report["elapsed_ms"] = round((time.monotonic() - started) * 1000)
        report["finished_at"] = datetime.datetime.now(datetime.UTC).isoformat()
        result = output / "result.json"
        result.write_bytes(canonical_bytes(report))
        result.chmod(0o600)
    print(canonical_bytes(report).decode())


if __name__ == "__main__":
    main()
