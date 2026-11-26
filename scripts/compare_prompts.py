"""Compare every classification prompt against the labelled test set.

Usage:
    uv run python scripts/compare_prompts.py
    uv run python scripts/compare_prompts.py --rpm 20
    uv run python scripts/compare_prompts.py --no-cache
"""

import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path

from stw_guide.config import get_settings
from stw_guide.db.llm_calls import make_recorder
from stw_guide.db.session import make_engine, make_sessionmaker
from stw_guide.llm.classify import LABELS, accuracy, classify, find_leaks
from stw_guide.llm.gateway import LLMUnavailable, build_gateway
from stw_guide.llm.prompts import read_prompt, versions

TESTSET = Path("eval/prompt_testset.jsonl")
CACHE = Path("eval/cache/classify.json")
NOTES = Path("NOTES.md")

START = "<!-- prompts:start -->"
END = "<!-- prompts:end -->"


def load_testset() -> tuple[list[dict], int]:
    """Load usable examples and count remaining TODO entries."""
    examples = []
    todo = 0

    for number, line in enumerate(
        TESTSET.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue

        row = json.loads(line)

        if row["label"] not in LABELS:
            raise SystemExit(f"{TESTSET} line {number}: label must be one of {LABELS}")

        if "TODO" in row["question"]:
            todo += 1
        else:
            examples.append({"n": number, **row})

    return examples, todo


def write_table(rows: list[dict], total: int) -> None:
    """Insert or replace the prompt comparison table in NOTES.md."""
    table = [
        START,
        "",
        "| Prompt version | Correct | Accuracy | Invalid replies | Avg tokens in |",
        "|---|---:|---:|---:|---:|",
    ]

    for row in rows:
        table.append(
            f"| {row['version']} | {row['correct']}/{total} "
            f"| {row['accuracy']:.0%} | {row['invalid']} "
            f"| {row['tokens_in']} |"
        )

    table.extend(["", END])

    text = NOTES.read_text(encoding="utf-8") if NOTES.exists() else "# Notes\n"
    block = "\n".join(table)

    if START in text and END in text:
        start = text.index(START)
        end = text.index(END) + len(END)
        text = text[:start] + block + text[end:]
    else:
        text = (
            text.rstrip() + "\n\n## D09 - Prompt versions compared\n\n" + block + "\n"
        )

    NOTES.write_text(text, encoding="utf-8")


async def run(args: argparse.Namespace) -> int:
    settings = get_settings()
    examples, todo = load_testset()

    if todo:
        print(
            f"note: {todo} test lines still say TODO "
            f"and are skipped ({len(examples)} usable)"
        )

    if len(examples) < 5:
        print("Write at least 5 real examples in the test set first.")
        return 1

    engine = make_engine(settings)
    gateway = build_gateway(
        settings,
        make_recorder(make_sessionmaker(engine)),
    )

    cache = (
        {}
        if args.no_cache or not CACHE.exists()
        else json.loads(CACHE.read_text(encoding="utf-8"))
    )

    CACHE.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    asked = 0

    try:
        for version in versions(settings.prompts_dir, "classify"):
            prompt = read_prompt(settings.prompts_dir, version)

            if "TODO" in prompt:
                print(f"skipped {version}: the file still contains TODO")
                continue

            leaks = find_leaks(
                prompt,
                [example["question"] for example in examples],
            )

            for leak in leaks:
                print(
                    f"LEAK in {version}: a test question is inside "
                    f"the prompt: {leak[:60]!r}"
                )

            results = []

            for example in examples:
                key = hashlib.sha256(
                    f"{prompt}\n\n{example['question']}".encode()
                ).hexdigest()

                if key not in cache:
                    got, reply = await classify(
                        gateway,
                        prompt,
                        version,
                        example["question"],
                    )

                    cache[key] = {
                        "got": got,
                        "reply": reply.text[:120],
                        "tokens_in": reply.tokens_in,
                    }

                    CACHE.write_text(
                        json.dumps(cache, ensure_ascii=False, indent=1),
                        encoding="utf-8",
                    )

                    asked += 1
                    await asyncio.sleep(60 / args.rpm)

                results.append({**example, **cache[key]})

            for miss in (r for r in results if r["got"] != r["label"]):
                print(
                    f"{version} missed line {miss['n']}: "
                    f"wanted {miss['label']}, got {miss['got']} "
                    f"(reply {miss['reply'][:40]!r}) "
                    f"{miss['question'][:60]!r}"
                )

            rows.append(
                {
                    "version": version,
                    "correct": sum(r["got"] == r["label"] for r in results),
                    "accuracy": accuracy(results),
                    "invalid": sum(r["got"] == "invalid" for r in results),
                    "tokens_in": round(
                        sum(r["tokens_in"] for r in results) / len(results)
                    ),
                }
            )

    except LLMUnavailable as error:
        print(f"Stopped: no model can answer ({str(error)[:160]})")
        print("Wait and rerun the same command. Completed answers are cached.")
        return 1

    finally:
        await engine.dispose()

    if not rows:
        print("No prompt version could be run. Check prompts/classify_v*.md")
        return 1

    write_table(rows, len(examples))

    print("\nPrompt comparison results:")
    for row in rows:
        print(
            f"{row['version']:<14} "
            f"{row['correct']:>2}/{len(examples)} "
            f"{row['accuracy']:.0%}"
        )

    print(f"\nModel calls made now: {asked} (remaining answers came from cache)")
    print(f"Comparison table saved to {NOTES}")
    return 0


def main() -> int:
    sys.stdout.reconfigure(errors="replace")

    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--rpm",
        type=float,
        default=12,
        help="Model calls per minute (default: 12)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Ignore the existing evaluation cache",
    )

    args = parser.parse_args()

    if args.rpm <= 0:
        parser.error("--rpm must be greater than zero")

    if not TESTSET.exists():
        print(f"{TESTSET} not found")
        return 1

    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
