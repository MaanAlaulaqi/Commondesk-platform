import unittest
from unittest.mock import Mock, patch

from qdrant_client import QdrantClient, models as q

from .search import COLLECTIONS, DIM, Store, point


class SearchPagesTest(unittest.TestCase):
    def setUp(self):
        self.db = QdrantClient(":memory:")
        with patch("worker.search.connect", return_value=self.db):
            self.store = Store()
        self.store.encoders = Mock()
        self.vector = [1.0, *([0.0] * (DIM - 1))]
        self.store.encoders.search_text.return_value = self.vector
        self.store.encoders.encode.return_value = self.vector
        self.addCleanup(self.db.close)

    def test_canonical_pages(self):
        name = self.store.ensure("dubai2024")
        points = []
        for n in range(103):
            for lang in ("th", "en"):
                cid = f"dv2-{n:03}"
                case = {
                    "id": cid,
                    "source": "dubai2024",
                    "language": lang,
                    "category": "parks",
                }
                points.append(
                    point(
                        cid + lang, case, self.vector, self.vector if n < 52 else None
                    )
                )
        self.db.upsert(name, points)

        def get(page, **overrides):
            return self.store.search(
                {"source": "dubai2024", "text": "trees", "page": page, **overrides}
            )

        results = [get(page) for page in (1, 2, 3)]
        self.assertEqual([len(r["items"]) for r in results], [50, 50, 3])
        self.assertEqual([r["total"] for r in results], [103] * 3)
        ids = [r["id"] for result in results for r in result["items"]]
        self.assertEqual(ids, sorted(set(ids)))
        self.assertEqual(self.store.encoders.search_text.call_count, 1)
        self.assertEqual(get(2, text="", image_b64="photo")["total"], 52)
        self.assertEqual(get(3, image_b64="photo")["total"], 103)
        self.assertEqual(get(1, filters={"category": "waste"})["total"], 0)
        self.assertEqual(get(4)["items"], [])

    def test_archive_pages(self):
        target = "archive_test"
        self.db.create_collection(
            target, vectors_config=q.VectorParams(size=DIM, distance=q.Distance.COSINE)
        )
        self.db.update_collection_aliases(
            [
                q.CreateAliasOperation(
                    create_alias=q.CreateAlias(
                        collection_name=target, alias_name=COLLECTIONS["archive"]
                    )
                )
            ]
        )
        self.db.upsert(
            target,
            [
                q.PointStruct(
                    id=i,
                    vector=self.vector,
                    payload={"report_id": f"{i:024x}", "source_offset": i},
                )
                for i in range(53)
            ],
        )
        self.store.archive = self.db
        first, second = [
            self.store.search({"source": "archive", "text": "drain", "page": n})
            for n in [1, 2]
        ]
        self.assertEqual(first["total"], 53)
        self.assertEqual(len(second["items"]), 3)
        ids = [r["id"] for page in [first, second] for r in page["items"]]
        self.assertEqual(len(set(ids)), 53)
