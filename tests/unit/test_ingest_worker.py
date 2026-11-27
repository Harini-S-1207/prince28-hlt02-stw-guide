"""The pure parts of the worker: planning, pacing, and getting a file. No Redis, no database."""

import httpx
import pytest

from stw_guide.workers.ingest import Pace, Permanent, get_file, plan, raw_url, sha256_of


def record(n: int, **changes) -> dict:
    base = {
        "url": f"https://x.test/{n}.pdf",
        "source": "x",
        "licence": "CC BY 4.0",
        "via": "http",
        "path": f"data/raw/x/{n}.pdf",
        "sha256": str(n) * 64,
        "status": "downloaded",
    }
    return base | changes


async def no_sleep(seconds: float) -> None:
    pass


def test_plan_takes_what_is_downloaded_new_and_wanted():
    records = [
        record(1),
        record(2, sha256="1" * 64),
        record(3),
        record(4, status="failed"),
        record(5, source="other"),
        record(6),
    ]
    known = {"f-" + "3" * 20}
    assert [r["url"][-5:] for r in plan(records, known)] == ["1.pdf", "5.pdf", "6.pdf"]
    assert [r["url"][-5:] for r in plan(records, known, source="x")] == [
        "1.pdf",
        "6.pdf",
    ]
    assert len(plan(records, known, limit=2)) == 2
    assert known == {"f-" + "3" * 20}


def test_raw_url_points_a_git_record_at_the_exact_commit():
    git = record(
        1,
        via="git",
        commit="05e6df7",
        url="https://github.com/fastapi/fastapi/blob/HEAD/docs/en/docs/index.md",
    )
    wanted = "https://raw.githubusercontent.com/fastapi/fastapi/05e6df7/docs/en/docs/index.md"
    assert raw_url(git) == wanted
    assert raw_url(record(2)) == "https://x.test/2.pdf"


async def test_pace_spreads_calls_evenly():
    slept: list[float] = []

    async def sleep(seconds: float) -> None:
        slept.append(seconds)

    pace = Pace(per_minute=60, clock=lambda: 100.0, sleep=sleep)
    for _ in range(3):
        await pace.wait()
    assert slept == [1.0, 2.0]


async def test_a_file_on_disk_is_used_and_a_hand_downloaded_one_is_never_fetched(
    tmp_path,
):
    here = tmp_path / "rules.md"
    here.write_text("# Rules", encoding="utf-8")
    assert await get_file(record(1, path=str(here)), tmp_path, client=None) == here

    by_hand = record(2, via="manual", path=str(tmp_path / "not-here.pdf"))
    with pytest.raises(Permanent, match="Downloaded manually"):
        await get_file(by_hand, tmp_path, client=None)


async def test_a_missing_file_is_downloaded_and_errors_are_sorted_into_two_kinds(
    tmp_path,
):
    def site(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /private/")
        status = {"/1.pdf": 200, "/2.pdf": 404, "/3.pdf": 503}.get(
            request.url.path, 200
        )
        return httpx.Response(status, content=b"%PDF-1.4 hello")

    async with httpx.AsyncClient(transport=httpx.MockTransport(site)) as client:
        got = await get_file(record(1), tmp_path, client, no_sleep)
        assert got.read_bytes() == b"%PDF-1.4 hello" and tmp_path in got.parents

        with pytest.raises(Permanent, match="404"):
            await get_file(record(2), tmp_path, client, no_sleep)

        with pytest.raises(RuntimeError, match="503"):
            await get_file(record(3), tmp_path, client, no_sleep)

        blocked = record(4, url="https://x.test/private/4.pdf")
        with pytest.raises(Permanent, match="robots"):
            await get_file(blocked, tmp_path, client, no_sleep)


def test_plan_returns_empty_when_every_record_is_already_handled():
    records = [
        record(1, status="failed"),
        record(2, status="pending"),
        record(3),
    ]
    known = {"f-" + "3" * 20}

    assert plan(records, known) == []


def test_raw_url_keeps_github_url_when_commit_is_missing():
    git = record(
        1,
        via="git",
        url="https://github.com/fastapi/fastapi/blob/HEAD/docs/index.md",
    )

    assert raw_url(git) == git["url"]


async def test_pace_does_not_delay_first_call_and_spaces_later_calls():
    now = [10.0]
    slept = []

    async def sleep(seconds: float) -> None:
        slept.append(seconds)
        now[0] += seconds

    pace = Pace(per_minute=2, clock=lambda: now[0], sleep=sleep)

    await pace.wait()
    await pace.wait()
    await pace.wait()

    assert slept == [30.0, 30.0]


async def test_existing_manual_file_is_used_without_downloading(tmp_path):
    here = tmp_path / "manual.pdf"
    here.write_bytes(b"%PDF-1.4 manual file")

    manual = record(1, via="manual", path=str(here))

    result = await get_file(manual, tmp_path, client=None)

    assert result == here
    assert result.read_bytes() == b"%PDF-1.4 manual file"


async def test_forbidden_download_is_a_permanent_error(tmp_path):
    def site(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /")
        return httpx.Response(403)

    async with httpx.AsyncClient(transport=httpx.MockTransport(site)) as client:
        with pytest.raises(Permanent, match="403"):
            await get_file(record(1), tmp_path, client, no_sleep)


def test_raw_url_does_not_rewrite_github_url_for_http_records():
    github = record(
        1,
        via="http",
        commit="05e6df7",
        url="https://github.com/fastapi/fastapi/blob/HEAD/docs/index.md",
    )

    assert raw_url(github) == github["url"]


@pytest.mark.parametrize("status_code", [429, 500, 502, 504])
async def test_retryable_http_errors_are_not_permanent(tmp_path, status_code):
    def site(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(
                200,
                text="User-agent: *\nAllow: /",
            )
        return httpx.Response(status_code)

    async with httpx.AsyncClient(transport=httpx.MockTransport(site)) as client:
        with pytest.raises(RuntimeError, match="download"):
            await get_file(
                record(1),
                tmp_path,
                client,
                no_sleep,
            )


def test_sha256_of_calculates_correct_hash(tmp_path):
    import hashlib

    file = tmp_path / "sample.txt"
    content = b"STW Guide ingestion test"
    file.write_bytes(content)

    assert sha256_of(file) == hashlib.sha256(content).hexdigest()


def test_sha256_of_handles_large_files(tmp_path):
    import hashlib

    file = tmp_path / "large.bin"
    content = b"A" * (2 * 1024 * 1024)
    file.write_bytes(content)

    assert sha256_of(file) == hashlib.sha256(content).hexdigest()


def test_plan_excludes_duplicate_content_hashes():
    records = [
        record(1),
        record(2, sha256="1" * 64),
        record(3, sha256="1" * 64),
    ]

    result = plan(records, set())

    assert len(result) == 1
    assert result[0]["url"].endswith("/1.pdf")


def test_plan_applies_source_filter_before_limit():
    records = [
        record(1, source="other"),
        record(2, source="x"),
        record(3, source="x"),
    ]

    result = plan(records, set(), source="x", limit=1)

    assert len(result) == 1
    assert result[0]["url"].endswith("/2.pdf")


def test_git_url_without_commit_is_not_rewritten():
    git = record(
        1,
        via="git",
        url="https://github.com/fastapi/fastapi/blob/HEAD/docs/index.md",
    )

    assert raw_url(git) == git["url"]
