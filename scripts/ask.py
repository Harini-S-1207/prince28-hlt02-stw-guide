"""Ask STW Guide through the chat API.

Usage:
    uv run python scripts/ask.py "Your question"
    uv run python scripts/ask.py "Your question" --json
"""

import argparse
import json
import sys
import time

import httpx


def parse_args():
    parser = argparse.ArgumentParser(description="Ask STW Guide")
    parser.add_argument("question", help="Question to send to STW Guide")
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8000/v1/chat",
        help="Chat API URL",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Use non-streaming mode and print JSON",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = {
        "message": args.question,
        "stream": not args.json,
    }

    started = time.perf_counter()
    first_token_ms = None
    answer_parts = []
    result = None
    error = None
    request_id = None

    try:
        with httpx.Client(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
            if args.json:
                response = client.post(args.url, json=payload)
                request_id = response.headers.get("X-Request-ID")
                response.raise_for_status()

                result = response.json()
                answer_parts.append(result.get("answer", ""))
                request_id = result.get("request_id") or request_id

            else:
                with client.stream(
                    "POST",
                    args.url,
                    json=payload,
                    headers={"Accept": "text/event-stream"},
                ) as response:
                    request_id = response.headers.get("X-Request-ID")
                    response.raise_for_status()

                    event_name = None

                    for line in response.iter_lines():
                        if line.startswith("event:"):
                            event_name = line[6:].strip()

                        elif line.startswith("data:"):
                            data = json.loads(line[5:].strip())

                            if event_name == "token":
                                token = data.get("text", "")

                                if token:
                                    if first_token_ms is None:
                                        first_token_ms = round(
                                            (time.perf_counter() - started) * 1000,
                                            2,
                                        )

                                    answer_parts.append(token)
                                    print(token, end="", flush=True)

                            elif event_name == "result":
                                result = data
                                request_id = data.get("request_id") or request_id

                            elif event_name == "error":
                                error = data.get("detail", "Unknown API error")

                        elif not line:
                            event_name = None

    except httpx.HTTPError as exc:
        print(f"\nAPI request failed: {exc}", file=sys.stderr)
        return 1

    except (ValueError, KeyError) as exc:
        print(f"\nInvalid API response: {exc}", file=sys.stderr)
        return 1

    total_ms = round((time.perf_counter() - started) * 1000, 2)
    answer = "".join(answer_parts)

    report = {
        "answer": answer,
        "streaming": not args.json,
        "time_to_first_token_ms": first_token_ms,
        "total_time_ms": total_ms,
        "provider": result.get("provider") if result else None,
        "model": result.get("model") if result else None,
        "tokens_in": result.get("tokens_in") if result else None,
        "tokens_out": result.get("tokens_out") if result else None,
        "latency_ms": result.get("latency_ms") if result else None,
        "attempts": result.get("attempts") if result else None,
        "fallback_used": result.get("fallback_used") if result else None,
        "cost_inr": result.get("cost_inr") if result else None,
        "request_id": request_id,
        "error": error,
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("\n\n--- Usage summary ---")
        print(f"First token: {first_token_ms} ms")
        print(f"Total time: {total_ms} ms")

        if result:
            print(f"Provider: {result.get('provider')}")
            print(f"Model: {result.get('model')}")
            print(
                f"Tokens: {result.get('tokens_in')} in / {result.get('tokens_out')} out"
            )
            print(f"Latency: {result.get('latency_ms')} ms")
            print(f"Fallback used: {result.get('fallback_used')}")
            print(f"Estimated cost: Rs {result.get('cost_inr')}")
            print(f"Request ID: {request_id}")

        if error:
            print(f"API error: {error}", file=sys.stderr)

    return 1 if error or result is None else 0


if __name__ == "__main__":
    sys.exit(main())
