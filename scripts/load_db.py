import asyncio
import hashlib
import json
from pathlib import Path

from sqlalchemy import select

from stw_guide.config import get_settings
from stw_guide.db.models import Document
from stw_guide.db.session import make_engine, make_sessionmaker

DATA_FILE = Path("data/sample_records.json")


async def load_records():
    records = json.loads(DATA_FILE.read_text(encoding="utf-8"))

    engine = make_engine(get_settings())
    SessionLocal = make_sessionmaker(engine)

    inserted = 0
    updated = 0
    unchanged = 0

    try:
        async with SessionLocal() as session:
            for record in records:
                content = json.dumps(record, sort_keys=True)
                sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()

                result = await session.execute(
                    select(Document).where(Document.external_id == record["id"])
                )
                document = result.scalar_one_or_none()

                values = {
                    "title": record["condition"],
                    "source_url": record.get("source", {}).get("url"),
                    "sha256": sha256,
                    "metadata_": record,
                }

                if document is None:
                    document = Document(
                        external_id=record["id"],
                        **values,
                    )
                    session.add(document)
                    inserted += 1

                elif document.sha256 != sha256:
                    for key, value in values.items():
                        setattr(document, key, value)
                    updated += 1

                else:
                    unchanged += 1

            await session.commit()

        print(f"Inserted: {inserted}")
        print(f"Updated: {updated}")
        print(f"Unchanged: {unchanged}")

    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(load_records())
