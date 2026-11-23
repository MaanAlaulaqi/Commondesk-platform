"""Offline request-boundary and artifact checks for the private CPU worker."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import BoundedSemaphore
from types import SimpleNamespace
from unittest.mock import Mock

from fastapi import HTTPException
from pydantic import ValidationError
from runtime import Request, Runtime, file_digest, release_revision


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.body = Request(text="Invented lamp report", source_language="en", target_language="ar")
        self.runtime = Runtime.__new__(Runtime)
        self.runtime.revision = "test-release"
        self.runtime.slot = BoundedSemaphore()
        self.runtime.directions = {"en:ar"}
        self.runtime.tokenizer = Mock()
        self.runtime.tokenizer.encode.return_value = ["example"]
        self.runtime.engine = Mock()

    def test_policy_is_checked_before_tokenization(self):
        self.runtime.directions = set()
        with self.assertRaises(HTTPException) as e:
            self.runtime.translate(self.body)
        self.assertEqual(e.exception.status_code, 422)
        self.runtime.tokenizer.encode.assert_not_called()

    def test_long_inputs_and_truncated_outputs_fail(self):
        self.runtime.tokenizer.encode.return_value = ["piece"] * 512
        with self.assertRaises(HTTPException):
            self.runtime.translate(self.body)
        self.runtime.engine.translate_batch.assert_not_called()
        self.runtime.tokenizer.encode.return_value = ["piece"]
        self.runtime.engine.translate_batch.return_value = [SimpleNamespace(hypotheses=[["unfinished"]])]
        with self.assertRaises(HTTPException):
            self.runtime.translate(self.body)
        self.assertTrue(self.runtime.slot.acquire(blocking=False))

    def test_private_input_contract(self):
        with self.assertRaises(ValidationError):
            Request(**self.body.model_dump(), photo="file")
        with self.assertRaises(ValidationError):
            Request(text="example", source_language="en", target_language="xx")

    def test_signed_off_policy_cannot_be_used_with_different_weights(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            hashes = {}
            for name in ("model.bin", "config.json", "spiece.model", "shared_vocabulary.json"):
                path = root / name
                path.write_bytes(b"fixture")
                hashes[name] = file_digest(path)
            with self.assertRaisesRegex(ValueError, "different model"):
                Runtime(root, {"sha256": hashes}, {"model_revision": "obsolete", "directions": []})
            expected = release_revision(hashes)
            (root / "model.bin").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "Invalid translation artifact"):
                Runtime(root, {"sha256": hashes}, {"model_revision": expected, "directions": []})


if __name__ == "__main__":
    unittest.main()
