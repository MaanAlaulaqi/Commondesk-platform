"""Supervise the private CPU translator independently of retrieval and its models."""

import hashlib
import hmac
import http.client
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

LANGUAGES = {"en", "ar", "th", "hi", "ur"}
DIRECTIONS = {s + ":" + t for s in LANGUAGES for t in LANGUAGES if s != t}
WEIGHTS = {"model.bin", "config.json", "spiece.model", "shared_vocabulary.json"}
WRITE_LIMIT = 96 * 1024
READ_LIMIT = 256 * 1024


class TranslationError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def unavailable():
    return TranslationError(503, "Private translation service unavailable")


def file_digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


class TranslationHost:
    def __init__(self, env):
        self.enabled = env.get("MT_COHOST") == "1"
        self.token = env.get("MT_INTERNAL_TOKEN", "")
        self.runtime_dir = Path(env.get("MT_RUNTIME_DIR", "/app/translator")).resolve()
        self.model_dir = Path(env.get("MT_MODEL_DIR", "/model")).resolve()
        self.manifest_path = Path(
            env.get("MT_MODEL_MANIFEST", "/release.json")
        ).resolve()
        self.policy_path = Path(
            env.get("MT_DIRECTION_POLICY", "/policy.json")
        ).resolve()
        self.coached_enabled = env.get("MT_AR_EN_COACHED") == "1"
        self.coached_dir = Path(
            env.get("MT_COACHED_MODEL_DIR", "/models/translation-ar-en")
        ).resolve()
        self.coached_manifest = self.runtime_dir / "coached-ar-en.json"
        self.coached_policy = self.runtime_dir / "coached-ar-en-policy.json"
        self.python = env.get("MT_PYTHON", sys.executable)
        self.threads = env.get("MT_THREADS", "2")
        try:
            self.idle_seconds = float(env.get("MT_IDLE_SECONDS", 600))
        except (TypeError, ValueError):
            self.idle_seconds = 0

        self.slot = threading.Lock()
        self.closing = threading.Event()
        self.child = None
        self.port = None
        self.child_manifest = None
        self.idle_timer = None

    def authorize(self, header):
        if not self.enabled:
            raise TranslationError(404, "Unknown route")
        if (
            len(self.token) < 32
            or not self.token.isascii()
            or not 0 < self.idle_seconds <= 86400
        ):
            raise unavailable()
        if (
            not header
            or not header.isascii()
            or not hmac.compare_digest(header, "Bearer " + self.token)
        ):
            raise TranslationError(401, "Private translation authorization required")

    def _release(self, source_language, target_language):
        if source_language is not None or target_language is not None:
            if (
                source_language not in LANGUAGES
                or target_language not in LANGUAGES
                or source_language == target_language
            ):
                raise TranslationError(422, "Invalid language pair")
        if self.coached_enabled and (source_language, target_language) == ("ar", "en"):
            return self.coached_dir, self.coached_manifest, self.coached_policy
        return self.model_dir, self.manifest_path, self.policy_path

    def manifest(self, source_language=None, target_language=None):
        release = self._release(source_language, target_language)
        return self._manifest(release)

    def _manifest(self, release):
        model_dir, manifest_path, policy_path = release
        # The cache identifies a specific release. This path reads metadata only. The child
        # independently verifies every mounted weight digest before accepting any report.
        try:
            files = json.loads(manifest_path.read_text())["sha256"]
            policy = json.loads(policy_path.read_text())
            if not isinstance(files, dict) or not WEIGHTS <= files.keys():
                raise ValueError
            for name, digest in files.items():
                if (
                    Path(name).name != name
                    or not re.fullmatch("[0-9a-f]{64}", digest)
                    or not (model_dir / name).is_file()
                ):
                    raise ValueError
            identity = {
                "weights": files,
                "runtime": file_digest(self.runtime_dir / "runtime.py"),
                "dependencies": file_digest(self.runtime_dir / "requirements.txt"),
            }
            revision = hashlib.sha256(
                json.dumps(identity, sort_keys=True).encode()
            ).hexdigest()
            directions = policy["directions"]
            if (
                policy["model_revision"] != revision
                or not isinstance(directions, list)
                or len(directions) != len(set(directions))
                or not set(directions) <= DIRECTIONS
            ):
                raise ValueError
            return {"model_revision": revision, "directions": sorted(directions)}
        except (OSError, KeyError, TypeError, ValueError):
            raise unavailable() from None

    def _start(self, release):
        model_dir, manifest_path, policy_path = release
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            # A bound socket handed directly to uvicorn avoids a port-allocation race.
            self.port = listener.getsockname()[1]
            fd = listener.fileno()
            env = {
                key: os.environ[key]
                for key in ("PATH", "HOME", "LANG", "LD_LIBRARY_PATH")
                if key in os.environ
            }
            env.update(
                MT_MODEL_DIR=str(model_dir),
                MT_MODEL_MANIFEST=str(manifest_path),
                MT_DIRECTION_POLICY=str(policy_path),
                MT_THREADS=self.threads,
                PYTHONDONTWRITEBYTECODE="1",
                HF_HUB_OFFLINE="1",
            )
            self.child = subprocess.Popen(
                [
                    self.python,
                    "-m",
                    "uvicorn",
                    "runtime:create_app",
                    "--factory",
                    "--fd",
                    str(fd),
                    "--no-access-log",
                    "--log-level",
                    "error",
                ],
                cwd=self.runtime_dir,
                pass_fds=(fd,),
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    def _request(self, path, data, timeout):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
        try:
            conn.request(
                "GET" if data is None else "POST",
                path,
                body=data,
                headers={"Content-Type": "application/json"},
            )
            response = conn.getresponse()
            body = response.read(READ_LIMIT + 1)
            if len(body) > READ_LIMIT:
                raise unavailable()
            if response.status == 422:
                raise TranslationError(422, "Translation unavailable for this report")
            if response.status == 429:
                raise TranslationError(429, "Translation worker is busy")
            if response.status != 200:
                raise unavailable()
            return json.loads(body)
        finally:
            conn.close()

    def _stop(self):
        if self.idle_timer:
            self.idle_timer.cancel()
            self.idle_timer = None
        child, self.child = self.child, None
        self.child_manifest = None
        self.port = None
        if child is not None and child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=2)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=2)

    def _arm_eviction(self):
        if self.idle_timer:
            self.idle_timer.cancel()

        # The identity prevents a timer waiting on the lock from evicting a newly used child.
        def evict():
            with self.slot:
                if self.idle_timer is timer:
                    self._stop()

        timer = threading.Timer(self.idle_seconds, evict)
        timer.daemon = True
        self.idle_timer = timer
        timer.start()

    def _ready(self, release, manifest, deadline):
        if (
            self.child is not None
            and self.child.poll() is None
            and self.child_manifest == manifest
        ):
            return
        self._stop()
        self._start(release)
        while (
            not self.closing.is_set()
            and self.child.poll() is None
            and time.monotonic() < deadline
        ):
            try:
                actual = self._request(
                    "/manifest", None, min(0.5, max(0.01, deadline - time.monotonic()))
                )
            except (OSError, http.client.HTTPException):
                self.closing.wait(0.1)
                continue
            if actual != manifest:
                raise unavailable()
            self.child_manifest = actual
            return
        raise unavailable()

    def translate(self, body):
        if (
            not isinstance(body, dict)
            or body.keys() != {"text", "source_language", "target_language"}
            or not isinstance(body["text"], str)
            or not 0 < len(body["text"]) <= 8000
            or not body["text"].strip()
            or not isinstance(body["source_language"], str)
            or not isinstance(body["target_language"], str)
        ):
            raise TranslationError(422, "Invalid report translation request")
        if not self.slot.acquire(timeout=2):
            raise TranslationError(429, "Translation worker is busy")
        try:
            release = self._release(body["source_language"], body["target_language"])
            manifest = self._manifest(release)
            if (
                body["source_language"] + ":" + body["target_language"]
                not in manifest["directions"]
            ):
                raise TranslationError(
                    422, "Translation unavailable for this language pair"
                )
            if self.closing.is_set():
                raise unavailable()
            deadline = time.monotonic() + 40
            try:
                self._ready(release, manifest, deadline)
                if self.closing.is_set() or time.monotonic() >= deadline:
                    raise unavailable()
                data = json.dumps(body, ensure_ascii=False).encode()
                result = self._request(
                    "/translate", data, max(0.01, deadline - time.monotonic())
                )
                if (
                    not isinstance(result, dict)
                    or result.get("model_revision") != manifest["model_revision"]
                    or not isinstance(result.get("text"), str)
                    or not result["text"].strip()
                ):
                    raise unavailable()
                return {
                    "text": result["text"],
                    "model_revision": manifest["model_revision"],
                }
            except TranslationError as exc:
                if exc.status == 503:
                    self._stop()
                raise
            except (OSError, http.client.HTTPException, ValueError):
                self._stop()
                raise unavailable() from None
            finally:
                if self.child is not None:
                    self._arm_eviction()
        finally:
            self.slot.release()

    def close(self):
        self.closing.set()
        child = self.child
        if child is not None and child.poll() is None:
            try:
                child.terminate()
            except ProcessLookupError:
                pass
        with self.slot:
            self._stop()
