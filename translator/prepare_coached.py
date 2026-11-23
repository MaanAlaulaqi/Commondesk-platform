"""Mint scoped, temporary object reads for the private Arabic model build."""

import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from huggingface_hub import HfApi, get_token


class SignedRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


def prepare(output):
    bucket = "rocketrat/traffy-retrieval-checkpoints-v1"
    token = get_token()
    if not token or not HfApi(token=token).bucket_info(bucket).private:
        raise RuntimeError("Authenticated private model bucket required")
    files = json.loads(Path(__file__).with_name("coached-ar-en.json").read_text())[
        "sha256"
    ]
    client = build_opener(SignedRedirect)
    links = {}
    for name in files:
        key = f"commondesk/mt-ar-followon/v1/serving/{files['model.bin']}/{name}"
        location = (
            "https://huggingface.co/buckets/"
            + bucket
            + "/resolve/"
            + quote(key, safe="")
        )
        req = Request(location, headers={"Authorization": "Bearer " + token})
        try:
            with client.open(req, timeout=30):
                raise RuntimeError("Single-object signed download unavailable")
        except HTTPError as exc:
            url = exc.headers.get("Location", "")
            if (
                exc.code != 302
                or urlsplit(url).scheme != "https"
                or not (urlsplit(url).hostname or "").endswith(".cdn.hf.co")
            ):
                raise RuntimeError("Private download grant unavailable") from None
            links[name] = url
    os.umask(0o077)
    with output.open("x") as f:
        json.dump(links, f)


if __name__ == "__main__":
    prepare(Path(sys.argv[1]))
