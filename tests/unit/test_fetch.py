"""The downloader, tested without the internet: httpx.MockTransport plays the website."""

import asyncio
import json
from pathlib import Path

import httpx
import pytest

from stw_guide.ingest import fetch
from stw_guide.ingest.fetch import Source, fetch_all

SITE = "https://docs.example.org"


def make_sources(count: int) -> list[Source]:
    licence = "CC BY 4.0"
    return [
        Source(f"{SITE}/guide/page-{i}.html", "Example Docs", licence)
        for i in range(count)
    ]


class FakeSite:
    """A tiny website. `plan` lists the status codes a path answers with before it says 200."""

    def __init__(
        self,
        robots: str | int = 404,
        plan: dict[str, list[int]] | None = None,
    ) -> None:
        self.robots = robots
        self.plan = plan or {}
        self.error_headers: dict[str, str] = {}
        self.hits: list[str] = []
        self.busy = 0
        self.max_busy = 0
        self.slept: list[float] = []

    async def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/robots.txt":
            if isinstance(self.robots, int):
                return httpx.Response(self.robots)
            return httpx.Response(200, text=self.robots)

        self.hits.append(path)
        self.busy += 1
        self.max_busy = max(self.max_busy, self.busy)
        await asyncio.sleep(0.005)
        self.busy -= 1

        queue = self.plan.get(path)
        status = queue.pop(0) if queue else 200
        if status != 200:
            return httpx.Response(status, headers=self.error_headers)
        return httpx.Response(200, html=f"<h1>{path}</h1>")

    async def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)

    async def run(
        self,
        sources: list[Source],
        root: Path,
        **options,
    ) -> dict[str, int]:
        transport = httpx.MockTransport(self.handler)
        async with httpx.AsyncClient(
            transport=transport,
            follow_redirects=True,
        ) as client:
            return await fetch_all(
                sources,
                root=root,
                client=client,
                sleep=self.sleep,
                per_host_delay=0,
                **options,
            )


def manifest(root: Path) -> list[dict]:
    lines = (root / "data" / "manifest.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


def raw_files(root: Path) -> list[Path]:
    return [p for p in (root / "data" / "raw").rglob("*") if p.is_file()]


async def test_downloads_files_and_records_where_they_came_from(tmp_path):
    counts = await FakeSite().run(make_sources(3), tmp_path)
    assert counts == {
        "downloaded": 3,
        "skipped": 0,
        "blocked": 0,
        "failed": 0,
    }

    record = manifest(tmp_path)[0]
    assert record["status"] == "downloaded"
    assert record["licence"] == "CC BY 4.0"

    saved = tmp_path / record["path"]
    assert saved.parent == tmp_path / "data" / "raw" / "example-docs"
    assert saved.suffix == ".html"
    assert saved.stat().st_size == record["bytes"]
    assert len(record["sha256"]) == 64


async def test_second_run_downloads_nothing(tmp_path):
    site = FakeSite()
    await site.run(make_sources(5), tmp_path)
    counts = await site.run(make_sources(5), tmp_path)

    assert counts["skipped"] == 5
    assert counts["downloaded"] == 0
    assert len(site.hits) == 5


async def test_resume_fetches_only_what_is_missing(tmp_path):
    site = FakeSite()
    await site.run(make_sources(3), tmp_path)
    counts = await site.run(make_sources(8), tmp_path)

    assert counts == {
        "downloaded": 5,
        "skipped": 3,
        "blocked": 0,
        "failed": 0,
    }
    assert len(site.hits) == 8
    assert len(set(site.hits)) == 8


async def test_deleted_file_is_downloaded_again(tmp_path):
    site = FakeSite()
    await site.run(make_sources(2), tmp_path)
    raw_files(tmp_path)[0].unlink()

    counts = await site.run(make_sources(2), tmp_path)
    assert counts["downloaded"] == 1
    assert counts["skipped"] == 1


async def test_retries_a_503_and_then_succeeds(tmp_path):
    site = FakeSite(plan={"/guide/page-0.html": [503, 503]})
    counts = await site.run(make_sources(1), tmp_path)

    assert counts["downloaded"] == 1
    assert manifest(tmp_path)[0]["attempts"] == 3
    assert len(site.slept) == 2


async def test_obeys_retry_after_on_429(tmp_path):
    site = FakeSite(plan={"/guide/page-0.html": [429]})
    site.error_headers = {"Retry-After": "7"}

    counts = await site.run(make_sources(1), tmp_path)
    assert counts["downloaded"] == 1
    assert site.slept
    assert site.slept[0] >= 7


async def test_gives_up_after_max_attempts_and_leaves_no_file(tmp_path):
    site = FakeSite(plan={"/guide/page-0.html": [500] * 10})
    counts = await site.run(make_sources(1), tmp_path, max_attempts=3)

    assert counts["failed"] == 1
    assert len(site.hits) == 3

    record = manifest(tmp_path)[0]
    assert record["status"] == "failed"
    assert record["http_status"] == 500
    assert raw_files(tmp_path) == []


async def test_404_is_not_retried(tmp_path):
    site = FakeSite(plan={"/guide/page-0.html": [404]})
    counts = await site.run(make_sources(1), tmp_path)

    assert counts["failed"] == 1
    assert len(site.hits) == 1
    assert site.slept == []


async def test_a_failed_file_is_tried_again_on_the_next_run(tmp_path):
    site = FakeSite(plan={"/guide/page-0.html": [404]})
    await site.run(make_sources(1), tmp_path)

    counts = await site.run(make_sources(1), tmp_path)
    assert counts["downloaded"] == 1


async def test_robots_disallow_means_never_requested(tmp_path):
    site = FakeSite(robots="User-agent: *\nDisallow: /guide/\n")
    counts = await site.run(make_sources(3), tmp_path)

    assert counts["blocked"] == 3
    assert site.hits == []


async def test_robots_longest_match_wins(tmp_path):
    site = FakeSite(robots="User-agent: *\nDisallow: /guide/\nAllow: /guide/page-1\n")
    counts = await site.run(make_sources(3), tmp_path)

    assert counts["blocked"] == 2
    assert site.hits == ["/guide/page-1.html"]


async def test_robots_server_error_blocks_the_whole_site(tmp_path):
    counts = await FakeSite(robots=503).run(make_sources(2), tmp_path)
    assert counts["blocked"] == 2


async def test_never_more_than_max_concurrency_at_once(tmp_path):
    site = FakeSite()
    await site.run(make_sources(20), tmp_path, max_concurrency=4)

    assert 1 < site.max_busy <= 4


async def test_broken_connection_leaves_no_half_file(tmp_path):
    async def body():
        yield b"<h1>first half"
        raise httpx.ReadError("connection lost")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(
            200,
            content=body(),
            headers={"Content-Type": "text/html"},
        )

    async def no_sleep(seconds: float) -> None:
        return None

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        counts = await fetch_all(
            make_sources(1),
            root=tmp_path,
            client=client,
            sleep=no_sleep,
            max_attempts=2,
        )

    assert counts["failed"] == 1
    assert manifest(tmp_path)[0]["error"] == "ReadError"
    assert raw_files(tmp_path) == []


def test_backoff_grows_but_stays_inside_its_limits():
    for attempt in range(12):
        ceiling = min(60.0, 2.0**attempt)
        assert all(0 <= fetch.backoff_delay(attempt) <= ceiling for _ in range(50))


def test_retry_after_understands_seconds_and_dates():
    assert fetch.retry_after_seconds("120") == 120.0
    assert fetch.retry_after_seconds("Wed, 21 Oct 2015 07:28:00 GMT") == 0.0
    assert fetch.retry_after_seconds("soon") is None
    assert fetch.retry_after_seconds(None) is None


def test_file_names_are_stable_and_safe():
    url = "https://example.org/files/Annual Report (2024): Final?.PDF"
    stem = fetch.file_stem(url)

    assert stem == fetch.file_stem(url)
    assert stem != fetch.file_stem(url + "x")
    assert all(ch.isalnum() or ch == "-" for ch in stem)

    assert fetch.pick_ext("https://example.org/a/b.PDF", "text/html") == ".pdf"
    assert (
        fetch.pick_ext("https://example.org/view.aspx?id=7", "application/pdf")
        == ".pdf"
    )
    assert fetch.pick_ext("https://example.org/thing", "weird/type") == ".bin"


def test_read_sources_skips_notes_and_duplicates(tmp_path):
    path = tmp_path / "sources.csv"
    path.write_text(
        "# my notes\n"
        "url,source,licence,title\n"
        "https://example.org/a.pdf,example,CC BY 4.0,Report A\n"
        "\n"
        "https://example.org/a.pdf,example,CC BY 4.0,Report A again\n"
        'https://example.org/b.pdf,example,"Public, cite the page",\n',
        encoding="utf-8",
    )

    sources = fetch.read_sources(path)

    assert [s.url for s in sources] == [
        "https://example.org/a.pdf",
        "https://example.org/b.pdf",
    ]
    assert sources[1].licence == "Public, cite the page"


def test_a_source_without_a_licence_is_refused(tmp_path):
    path = tmp_path / "sources.csv"
    path.write_text("url,source,licence,title\nhttps://example.org/a.pdf,example,,\n")

    with pytest.raises(ValueError, match="licence"):
        fetch.read_sources(path)


def test_retry_after_accepts_timezone_naive_http_date():
    assert fetch.retry_after_seconds("Wed, 21 Oct 2015 07:28:00") == 0.0


def test_read_sources_rejects_invalid_url(tmp_path):
    path = tmp_path / "sources.csv"
    path.write_text(
        "url,source,licence,title\nftp://example.org/a.pdf,example,CC BY 4.0,Report\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="http"):
        fetch.read_sources(path)


def test_manifest_ignores_corrupt_lines_and_repairs_missing_newline(tmp_path):
    path = tmp_path / "manifest.jsonl"
    valid = json.dumps(
        {
            "url": "https://example.org/a.pdf",
            "status": "downloaded",
        }
    )
    path.write_text(valid + "\n{invalid json}", encoding="utf-8")

    result = fetch.Manifest(path)

    assert "https://example.org/a.pdf" in result.records
    assert path.read_text(encoding="utf-8").endswith("\n")


async def test_robots_network_error_blocks_download():
    def handler(request):
        raise httpx.ConnectError("offline", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        robots = fetch.Robots(client)
        allowed, delay = await robots.check("https://example.org/guide.pdf")

    assert allowed is False
    assert delay == 0.0


async def test_download_rejects_file_over_size_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch, "MAX_BYTES", 3)

    counts = await FakeSite().run(make_sources(1), tmp_path)

    assert counts["failed"] == 1
    assert raw_files(tmp_path) == []


async def test_excessive_retry_after_stops_without_waiting(tmp_path):
    site = FakeSite(plan={"/guide/page-0.html": [429]})
    site.error_headers = {"Retry-After": "9999"}

    counts = await site.run(make_sources(1), tmp_path)

    assert counts["failed"] == 1
    assert len(site.hits) == 1
    assert site.slept == []
    assert "run again later" in manifest(tmp_path)[0]["error"]


async def test_non_transport_http_error_is_not_retried(tmp_path):
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        raise httpx.DecodingError("invalid response", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        counts = await fetch_all(
            make_sources(1),
            root=tmp_path,
            client=client,
            sleep=asyncio.sleep,
            per_host_delay=0,
        )

    assert counts["failed"] == 1
    assert manifest(tmp_path)[0]["attempts"] == 1


async def test_repeated_identical_failure_does_not_duplicate_manifest(tmp_path):
    site = FakeSite(plan={"/guide/page-0.html": [404, 404]})

    await site.run(make_sources(1), tmp_path)
    first_count = len(manifest(tmp_path))

    await site.run(make_sources(1), tmp_path)
    second_count = len(manifest(tmp_path))

    assert first_count == 1
    assert second_count == first_count


async def test_on_result_callback_receives_download_result(tmp_path):
    received = []

    counts = await FakeSite().run(
        make_sources(1),
        tmp_path,
        on_result=received.append,
    )

    assert counts["downloaded"] == 1
    assert len(received) == 1
    assert received[0]["status"] == "downloaded"


def test_make_client_creates_configured_async_client():
    client = fetch.make_client(max_concurrency=2)

    try:
        assert isinstance(client, httpx.AsyncClient)
        assert client.headers["User-Agent"] == fetch.USER_AGENT
        assert client.follow_redirects is True
    finally:
        # Close the client to avoid leaking connections.
        import asyncio

        asyncio.run(client.aclose())


async def test_fetch_all_closes_client_it_creates(tmp_path, monkeypatch):
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(404))
    )
    monkeypatch.setattr(fetch, "make_client", lambda max_concurrency: client)

    await fetch.fetch_all([], root=tmp_path)

    assert client.is_closed
