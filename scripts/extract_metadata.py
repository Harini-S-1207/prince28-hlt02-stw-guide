"""Fill documents.metadata with validated extraction records.

Examples:
  uv run python scripts/extract_metadata.py --limit 5
  uv run python scripts/extract_metadata.py
  uv run python scripts/extract_metadata.py --retry-failed
  uv run python scripts/extract_metadata.py --schema
"""

import argparse
import asyncio
import sys
import time

from stw_guide.config import get_settings
from stw_guide.db.llm_calls import make_recorder
from stw_guide.db.session import make_engine, make_sessionmaker
from stw_guide.llm.doc_meta import DocMeta
from stw_guide.llm.extract import run
from stw_guide.llm.gateway import build_gateway
from stw_guide.llm.prompts import latest, read_prompt


async def main_async(args: argparse.Namespace) -> int:
    settings = get_settings()
    version = latest(settings.prompts_dir, "extract")
    prompt = read_prompt(settings.prompts_dir, version)

    engine = make_engine(settings)
    sessionmaker = make_sessionmaker(engine)
    gateway = build_gateway(settings, make_recorder(sessionmaker))
    started = time.perf_counter()

    try:
        counts = await run(
            sessionmaker,
            gateway,
            DocMeta,
            prompt,
            version,
            limit=args.limit,
            rpm=args.rpm,
            chars=args.chars,
            retry_failed=args.retry_failed,
            native=args.schema,
        )
    finally:
        await engine.dispose()

    print(
        f"prompt={version} pending={counts['pending']} "
        f"ok={counts['ok']} repaired={counts['repaired']} "
        f"failed={counts['failed']} "
        f"tokens_in={counts['tokens_in']} "
        f"tokens_out={counts['tokens_out']} "
        f"cost=Rs {counts['micro_inr'] / 1_000_000:.4f} "
        f"seconds={time.perf_counter() - started:.0f}"
    )

    if counts["stopped"]:
        print(
            "Not finished. Wait a few minutes and run the same command again: "
            "it continues."
        )

    return 1 if counts["stopped"] else 0


def main() -> int:
    sys.stdout.reconfigure(errors="replace")
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--limit", type=int, default=0, help="at most N documents")
    parser.add_argument(
        "--rpm",
        type=float,
        default=12,
        help="documents per minute (default 12)",
    )
    parser.add_argument(
        "--chars",
        type=int,
        default=6000,
        help="characters read per document",
    )
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="also retry failed documents",
    )
    parser.add_argument(
        "--schema",
        action="store_true",
        help="send the JSON schema to the provider",
    )
    return asyncio.run(main_async(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
