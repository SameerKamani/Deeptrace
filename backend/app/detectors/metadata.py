from __future__ import annotations

import json
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
                    # Safely convert arbitrary objects (like IFDRational) to string
                    exif[tag] = str(value)
        except Exception as exc:
            return EvidenceSignal(
                id=self.id,
                name=self.name,
                category=self.category,
                status=SignalStatus.ERROR,
                reliability=0.0,
                summary="Failed to extract EXIF metadata payload.",
                observations=[f"EXIF extraction raised an exception: {exc}"],
                supports=SignalSupport.UNKNOWN,
            )

        observations = []
        supports = SignalSupport.UNKNOWN
        reliability = 0.2

        if not exif:
            observations.append("CRITICAL: Image contains absolutely zero EXIF metadata. Stripped or procedurally generated.")
            return EvidenceSignal(
                id=self.id,
                name=self.name,
                category=self.category,
                status=SignalStatus.WARNING,
                reliability=0.3,
                summary="Metadata is completely absent.",
                observations=observations,
                metrics={"exif_count": 0},
                supports=SignalSupport.UNKNOWN,
                notes="Missing metadata is common in social media but highly suspect in forensic analysis."
            )

        make = exif.get("Make", "").lower()
        model = exif.get("Model", "").lower()
        software = exif.get("Software", "").lower()

        # Generative Engine Fingerprints
        ai_engines = ["midjourney", "dall-e", "stable diffusion", "openai", "comfyui", "automatic1111"]
        is_ai_stamped = any(engine in software for engine in ai_engines) or any(engine in make or engine in model for engine in ai_engines)

        if is_ai_stamped:
            observations.append(f"AI SIGNATURE DETECTED: Software/Make explicitly identifies as generative ({software or make}).")
            return EvidenceSignal(
                id=self.id,
                name=self.name,
                category=self.category,
                status=SignalStatus.OK,
                reliability=0.95,
                summary="Explicit generative metadata trace found.",
                observations=observations,
                metrics={"exif_count": len(exif)},
                supports=SignalSupport.AI_GENERATED,
            )

        # Standard Camera Logic
        if make or model:
            observations.append(f"Hardware footprint: {make.capitalize() or 'Unknown'} {model.capitalize() or 'Unknown'}")
            
            # Check for realistic physical optics tags
            important_tags = ["FocalLength", "ExposureTime", "ISOSpeedRatings", "FNumber"]
            found_physics_tags = sum(1 for tag in important_tags if tag in exif)
            
            if found_physics_tags >= 2:
                observations.append(f"Physical optics data present ({found_physics_tags}/{len(important_tags)} core tags).")
                supports = SignalSupport.AUTHENTIC
                reliability = 0.6
                summary = "Consistent physical camera footprint found."
            else:
                observations.append("Camera make/model exists, but deep optical physics data is missing. Potentially spoofed.")
                supports = SignalSupport.INCONCLUSIVE
                reliability = 0.4
                summary = "Hardware footprint found but optical data is incomplete."
                
        else:
            observations.append("EXIF block initialized but lacks explicit hardware (Make/Model) identifiers.")
            summary = "Incomplete standard metadata."

        if software and not is_ai_stamped:
            observations.append(f"Post-processing software trace: {software}")

        return EvidenceSignal(
            id=self.id,
            name=self.name,
            category=self.category,
            status=SignalStatus.OK,
            reliability=reliability,
            summary=summary,
            observations=observations,
            metrics={"exif_count": len(exif)},
            supports=supports,
            notes="Metadata can be manipulated; this signal evaluates structural consistency of the EXIF block.",
        )
