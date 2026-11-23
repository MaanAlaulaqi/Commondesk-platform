"""Private, loopback-only supervisor integration. Run with the API verification venv."""

import concurrent.futures
import hashlib
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from worker.translation_host import TranslationError, TranslationHost, file_digest

FIXTURE = """
import json, os
from pathlib import Path
from fastapi import FastAPI, HTTPException

def create_app():
    assert not os.getenv("MT_INTERNAL_TOKEN")
    with open("launches", "a") as f:
        f.write("launch\\n")
    policy = json.loads(Path(os.environ["MT_DIRECTION_POLICY"]).read_text())
    app = FastAPI()
    @app.get("/manifest")
    def manifest():
        return policy
    @app.post("/translate")
    def translate(body:dict):
        if body["text"] == "reject":
            raise HTTPException(422, detail=body)
        return {"text": "synthetic output", "model_revision":policy["model_revision"]}
    return app
"""


class TranslationHostTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        files = {}
        for name in [
            "model.bin",
            "config.json",
            "spiece.model",
            "shared_vocabulary.json",
        ]:
            path = self.root / name
            path.write_text("invented fixture weights")
            files[name] = file_digest(path)
        (self.root / "runtime.py").write_text(FIXTURE)
        (self.root / "requirements.txt").write_text("")
        manifest = self.root / "release.json"
        manifest.write_text(json.dumps({"sha256": files}))
        ident = {
            "weights": files,
            "runtime": file_digest(self.root / "runtime.py"),
            "dependencies": file_digest(self.root / "requirements.txt"),
        }
        self.revision = hashlib.sha256(
            json.dumps(ident, sort_keys=True).encode()
        ).hexdigest()
        self.policy = self.root / "policy.json"
        self.set_policy(["en:hi"])
        self.env = dict(
            MT_COHOST="1",
            MT_RUNTIME_DIR=tmp.name,
            MT_MODEL_DIR=tmp.name,
            MT_MODEL_MANIFEST=str(manifest),
            MT_DIRECTION_POLICY=str(self.policy),
            MT_INTERNAL_TOKEN="f" * 32,
            MT_PYTHON=sys.executable,
            MT_IDLE_SECONDS="0.5",
        )
        self.host = TranslationHost(self.env)
        self.addCleanup(self.host.close)
        self.body = dict(
            source_language="en", target_language="hi", text="invented report"
        )

    def set_policy(self, directions):
        self.policy.write_text(
            json.dumps({"model_revision": self.revision, "directions": directions})
        )

    def check_status(self, status, call, *args):
        with self.assertRaises(TranslationError) as failure:
            call(*args)
        self.assertEqual(failure.exception.status, status)
        return str(failure.exception)

    def test_auth_and_manifest_do_not_spawn(self):
        self.check_status(401, self.host.authorize, None)
        self.check_status(401, self.host.authorize, "Bearer nope")
        self.host.authorize("Bearer " + "f" * 32)
        self.assertEqual(self.host.manifest()["model_revision"], self.revision)
        self.assertIsNone(self.host.child)
        self.assertFalse((self.root / "launches").exists())
        self.set_policy([])
        self.check_status(422, self.host.translate, self.body)
        self.assertIsNone(self.host.child)
        (self.root / "requirements.txt").write_text("changed")
        self.check_status(503, self.host.manifest)
        self.check_status(404, TranslationHost({}).authorize, None)

    def test_concurrent_use_eviction_and_crash_recovery(self):
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            futures = [pool.submit(self.host.translate, self.body) for _ in range(2)]
            for future in futures:
                self.assertEqual(future.result()["text"], "synthetic output")
        self.assertEqual((self.root / "launches").read_text().count("launch"), 1)
        first = self.host.child
        first.kill()
        first.wait(timeout=2)
        self.assertEqual(
            self.host.translate(self.body)["model_revision"], self.revision
        )
        child = self.host.child
        self.assertIsNot(first, child)
        self.assertEqual((self.root / "launches").read_text().count("launch"), 2)
        deadline = time.monotonic() + 5
        while child.poll() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertIsNotNone(child.poll())
        self.assertEqual(self.host.manifest()["model_revision"], self.revision)
        self.assertEqual((self.root / "launches").read_text().count("launch"), 2)
        self.assertEqual(self.host.translate(self.body)["text"], "synthetic output")

    def test_manual_arabic_route_swaps_the_only_child(self):
        self.set_policy(["ar:en", "en:hi"])
        coached = self.root / "coached"
        coached.mkdir()
        for name in (
            "model.bin",
            "config.json",
            "spiece.model",
            "shared_vocabulary.json",
        ):
            (coached / name).write_text("coached fixture")
        files = {p.name: file_digest(p) for p in coached.iterdir()}
        identity = {
            "weights": files,
            "runtime": file_digest(self.root / "runtime.py"),
            "dependencies": file_digest(self.root / "requirements.txt"),
        }
        revision = hashlib.sha256(
            json.dumps(identity, sort_keys=True).encode()
        ).hexdigest()
        (self.root / "coached-ar-en.json").write_text(json.dumps({"sha256": files}))
        (self.root / "coached-ar-en-policy.json").write_text(
            json.dumps({"model_revision": revision, "directions": ["ar:en"]})
        )
        host = TranslationHost(
            dict(self.env, MT_AR_EN_COACHED="1", MT_COACHED_MODEL_DIR=str(coached))
        )
        self.addCleanup(host.close)
        ar = dict(self.body, source_language="ar", target_language="en")
        self.assertEqual(host.manifest("ar", "en")["model_revision"], revision)
        self.assertEqual(host.manifest()["model_revision"], self.revision)
        self.assertEqual(
            self.host.manifest("ar", "en")["model_revision"], self.revision
        )
        self.assertEqual(host.translate(ar)["model_revision"], revision)
        arabic_child = host.child
        self.assertEqual(host.translate(self.body)["model_revision"], self.revision)
        self.assertIsNotNone(arabic_child.poll())
        self.check_status(422, host.manifest, "ar", None)
        (coached / "model.bin").unlink()
        self.check_status(503, host.manifest, "ar", "en")
        self.assertEqual(host.manifest("en", "hi")["model_revision"], self.revision)

    def test_invalid_body_and_lifecycle(self):
        self.check_status(422, self.host.translate, dict(self.body, photo="x"))
        self.check_status(422, self.host.translate, dict(self.body, text=" " * 10))
        self.check_status(
            422, self.host.translate, dict(self.body, target_language="ur")
        )
        msg = self.check_status(
            422, self.host.translate, dict(self.body, text="reject")
        )
        self.assertNotIn("reject", msg)
        child = self.host.child
        self.assertIsNone(child.poll())
        self.host.close()
        self.assertIsNotNone(child.poll())
        self.check_status(503, self.host.translate, self.body)

    def test_corrupt_child_identity_is_rejected_before_forwarding(self):
        original = self.host._request

        def skew(path, data, timeout):
            result = original(path, data, timeout)
            if path == "/manifest":
                result["model_revision"] = "wrong"
            else:
                self.fail("text was sent to mismatched child")
            return result

        with patch.object(self.host, "_request", side_effect=skew):
            self.check_status(503, self.host.translate, self.body)
        self.assertIsNone(self.host.child)


if __name__ == "__main__":
    unittest.main()
