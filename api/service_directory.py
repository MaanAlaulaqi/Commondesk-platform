"""Resolve the current case's routing options from verified scope and a local catalog."""

import json
import os
import re
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

SERVICE = {
    "id": "dubai_rta_madinati",
    "name": "RTA Madinati",
    "url": "https://rta.ae/wps/portal/rta/ae/home/promotion/madinati-service",
    "kind": "public_authority",
    "fictional": False,
}
PRIVATE_CATEGORIES = ("private_plumbing", "private_electrical")
ServiceContext = Literal["unknown", "public_asset", "private_premises", "emergency"]
EMERGENCY_TERMS = (
    "emergency",
    "electric shock",
    "exposed wire",
    "live wire",
    "sparking",
    "sparks",
    "on fire",
    "smoke",
    "electrocution",
    "طوارئ",
    "شرر",
    "حريق",
    "صعق",
    "مكشوف",
    "آگ",
    "چنگار",
    "بجلی کا جھٹکا",
    "ہنگامی",
    "करंट",
    "आग",
    "चिंगारी",
    "आपात",
    "ไฟไหม้",
    "ไฟรั่ว",
    "ประกายไฟ",
    "สายไฟขาด",
    "ฉุกเฉิน",
)
PUBLIC_TERMS = (
    "public drain",
    "street drain",
    "streetlight",
    "street light",
    "public road",
    "إنارة الشارع",
    "بالوعة الشارع",
    "نالی سڑک",
    "سڑک کی بتی",
    "सड़क की नाली",
    "स्ट्रीट लाइट",
    "ไฟถนน",
    "ท่อระบายน้ำสาธารณะ",
)
PRIVATE_TERMS = (
    "private property",
    "private premises",
    "inside my apartment",
    "داخل شقتي",
    "میرے فلیٹ",
    "मेरे फ्लैट",
    "ในห้องชุด",
)


class Provider(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str = Field(pattern=r"^private_[a-z0-9_]{1,70}$")
    name: str = Field(min_length=1, max_length=100)
    category: Literal["private_plumbing", "private_electrical"]
    enabled: bool = False
    fictional: bool = False
    url: str | None = None
    approved_source: str | None = None
    allowed_districts: list[str] | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_evidence(self):
        if not self.name.strip() or not self.name.isprintable():
            raise ValueError("Invalid provider name")
        if self.allowed_districts is not None and any(
            not d.strip() or not d.isprintable() for d in self.allowed_districts
        ):
            raise ValueError("Invalid service area")
        if self.fictional:
            if self.url or self.approved_source:
                raise ValueError("Fixture providers cannot link to businesses")
        elif self.enabled:
            if not self.url or self.url != self.approved_source:
                raise ValueError("An enabled business requires its approved source URL")
        for link in (self.url, self.approved_source):
            if link:
                parts = urlsplit(link)
                if (
                    parts.scheme != "https"
                    or not parts.hostname
                    or parts.username
                    or parts.password
                    or not re.fullmatch(r"[a-zA-Z0-9.-]+", parts.hostname)
                    or any(c.isspace() or c == "\\" for c in link)
                ):
                    raise ValueError("Invalid provider HTTPS URL")
        return self


def private_options(category, district=None):
    path = os.getenv("SERVICE_CATALOG_PATH")
    if not path:
        return []
    try:
        raw = json.loads(Path(path).read_text())
        if not isinstance(raw, list):
            return []
        records = [Provider.model_validate(entry) for entry in raw]
        if len({r.id for r in records}) != len(records):
            return []
    except (OSError, ValueError, ValidationError):
        return []
    return [
        dict(
            id=r.id,
            name=r.name,
            url=r.url,
            kind="private_directory",
            fictional=r.fictional,
        )
        for r in records
        if r.enabled
        and r.category == category
        and (
            r.allowed_districts is None
            or (district or "").strip().casefold()
            in {d.strip().casefold() for d in r.allowed_districts}
        )
    ]


def service_options(category, row):
    if row["source"] not in ("live", "seed"):
        return []
    context = row.get("service_context") or "unknown"
    if context not in ("unknown", "public_asset", "private_premises"):
        return []
    proposal = row["proposal"] or {}
    original = (row.get("text") or "").casefold()
    if proposal.get("urgency_reason") == "reported_hazard_keyword" or any(
        t in original for t in EMERGENCY_TERMS
    ):
        return []
    if row["source"] == "seed":
        # The verified seed's original offer and scope are authoritative. Reclassification
        # cannot turn historical evidence into an eligible Dubai service case.
        return (
            [SERVICE]
            if (
                context in ("unknown", "public_asset")
                and category == proposal.get("category")
                and SERVICE["id"] in (proposal.get("service_options") or [])
            )
            else []
        )
    if (
        context != "private_premises"
        and category in ("footpath", "transit")
        and not any(t in original for t in PRIVATE_TERMS)
    ):
        return [SERVICE]
    if (
        context == "private_premises"
        and category in PRIVATE_CATEGORIES
        and row["intent"] == "complaint"
        and (row["final_urgency"] or row["suggested_urgency"]) in ("moderate", "low")
        and not any(t in original for t in PUBLIC_TERMS)
    ):
        return private_options(category, row.get("district"))
    return []
