from __future__ import annotations

from typing import Any, Dict

from PIL import ExifTags

from ..models.evidence import EvidenceSignal, SignalStatus, SignalSupport
from .base import Detector


class MetadataDetector(Detector):
    id = "metadata_analysis"
    name = "Metadata & Provenance"
    category = "metadata"

    async def analyze(self, image, context: Dict[str, Any]) -> EvidenceSignal:
        exif = {}
        try:
            raw_exif = image.getexif()
            if raw_exif:
                for key, value in raw_exif.items():
                    tag = ExifTags.TAGS.get(key, str(key))
                    exif[tag] = value
        except Exception as exc:
            return EvidenceSignal(
                id=self.id,
                name=self.name,
                category=self.category,
                status=SignalStatus.ERROR,
                reliability=0.0,
                summary="Failed to extract EXIF metadata.",
                observations=[f"EXIF extraction error: {exc}"],
                supports=SignalSupport.UNKNOWN,
            )

        observations = []
        supports = SignalSupport.UNKNOWN
        reliability = 0.2

        if exif:
            make = exif.get("Make")
            model = exif.get("Model")
            if make or model:
                observations.append(f"Camera make: {make or 'unknown'}")
                observations.append(f"Camera model: {model or 'unknown'}")
                supports = SignalSupport.AUTHENTIC
                reliability = 0.35
            else:
                observations.append("EXIF metadata present but camera identifiers missing.")
        else:
            observations.append("No EXIF metadata found.")

        return EvidenceSignal(
            id=self.id,
            name=self.name,
            category=self.category,
            status=SignalStatus.OK,
            reliability=reliability,
            summary="Metadata review completed.",
            observations=observations,
            metrics={"exif_count": len(exif)},
            supports=supports,
            notes="Missing metadata alone does not imply AI generation.",
        )
