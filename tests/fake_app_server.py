from __future__ import annotations

import argparse
import json
import sys


def send(message: dict) -> None:
    print(json.dumps(message, separators=(",", ":")), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--error", action="store_true")
    parser.add_argument("--exit-on-initialize", action="store_true")
    parser.add_argument("--malformed", action="store_true")
    args = parser.parse_args()
    for line in sys.stdin:
        message = json.loads(line)
        if message.get("method") == "initialized":
            continue
        request_id = message.get("id")
        method = message.get("method")
        if method == "initialize":
            if args.exit_on_initialize:
                print(
                    "startup failed Authorization: Bearer secret-value",
                    file=sys.stderr,
                    flush=True,
                )
                return 23
            if args.malformed:
                print("not-json", flush=True)
                continue
            send({"id": request_id, "result": {"platformFamily": "windows"}})
        elif args.error:
            send({"id": request_id, "error": {"code": -32000, "message": "test error"}})
        elif method == "account/read":
            send(
                {
                    "id": request_id,
                    "result": {
                        "account": {"type": "chatgpt", "email": None, "planType": "plus"},
                        "requiresOpenaiAuth": True,
                    },
                }
            )
        elif method == "account/rateLimits/read":
            send(
                {
                    "id": request_id,
                    "result": {
                        "rateLimits": {
                            "limitId": "codex",
                            "primary": {
                                "usedPercent": 25,
                                "windowDurationMins": 300,
                                "resetsAt": 1_800_000_000,
                            },
                            "secondary": {
                                "usedPercent": 40,
                                "windowDurationMins": 10080,
                                "resetsAt": 1_800_500_000,
                            },
                        }
                    },
                }
            )
        else:
            send({"id": request_id, "result": {}})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

