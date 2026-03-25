from __future__ import annotations

import os
from typing import Any, Dict, Optional

import numpy as np
import torch
from PIL import Image

from ..core.config import settings
from ..models.evidence import EvidenceSignal, SignalStatus, SignalSupport
from .base import Detector
from .spectral_model import SpectralFusionModel, load_state_dict_from_path


class SpectralArtifactDetector(Detector):
    id = "spectral_artifacts"
    name = "Spectral Artifacts"
    category = "spectral"

    _model: Optional[SpectralFusionModel] = None
    _model_error: Optional[str] = None

    def _load_model(self, model_path: str) -> Optional[str]:
        if self._model is not None or self._model_error is not None:
            return self._model_error

        try:
            state = load_state_dict_from_path(model_path)
            model = SpectralFusionModel()
            missing, unexpected = model.load_state_dict(state, strict=False)
            model.eval()
            self._model = model
            if missing or unexpected:
                details = []
                if missing:
                    details.append(f"missing keys: {len(missing)}")
                if unexpected:
                    details.append(f"unexpected keys: {len(unexpected)}")
                self._model_error = "; ".join(details)
        except Exception as exc:
            self._model_error = f"Failed to load spectral model: {exc}"
        return self._model_error

    async def analyze(self, image, context: Dict[str, Any]) -> EvidenceSignal:
        model_path = settings.spectral_model_path
        if not os.path.exists(model_path):
            return EvidenceSignal(
                id=self.id,
                name=self.name,
                category=self.category,
                status=SignalStatus.UNAVAILABLE,
                reliability=0.0,
                summary="This check could not run because the spectral model is not available.",
                what_checked="We look for hidden frequency patterns that often appear in AI-generated images.",
                what_found="The spectral detector was unavailable for this image.",
                why_it_matters="Without this check, we lose one useful way of spotting generation artifacts that are hard to see by eye.",
                caveat="This does not say anything about the image itself. It only means this detector was not available.",
                observations=[f"Expected model at {model_path}"],
                supports=SignalSupport.UNKNOWN,
                notes="Place the spectral model directory or file at the configured path.",
            )

        load_error = self._load_model(model_path)
        if self._model is None:
            return EvidenceSignal(
                id=self.id,
                name=self.name,
                category=self.category,
                status=SignalStatus.ERROR,
                reliability=0.0,
                summary="This check failed because the spectral model could not be loaded.",
                what_checked="We look for hidden frequency patterns that often appear in AI-generated images.",
                what_found="The detector crashed before it could analyze the image.",
                why_it_matters="Without this check, the final result has less information about hidden generation artifacts.",
                caveat="This is a detector failure, not evidence for or against authenticity.",
                observations=[load_error or "Unknown model loading error."],
                supports=SignalSupport.UNKNOWN,
            )

        resized = image.resize((settings.spectral_input_size, settings.spectral_input_size), Image.BICUBIC)
        arr = np.asarray(resized, dtype=np.float32) / 255.0
        tensor = torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0)

        if settings.spectral_normalize:
            mean = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)
            std = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)
            tensor = (tensor - mean) / std

        with torch.no_grad():
            logits = self._model(tensor)
            probs = torch.softmax(logits, dim=1).squeeze(0).cpu().numpy()

        ai_index = settings.spectral_ai_index
        ai_prob = float(probs[ai_index])
        auth_prob = float(probs[1 - ai_index]) if len(probs) > 1 else 1.0 - ai_prob

        if ai_prob >= 0.6:
            supports = SignalSupport.AI_GENERATED
            summary = "The spectral scan found patterns that lean toward AI generation."
            what_found = (
                f"The model gave this image a strong AI-style frequency reading "
                f"({ai_prob:.0%} AI vs {auth_prob:.0%} authentic)."
            )
            why_it_matters = (
                "AI-generated images often leave behind hidden frequency patterns that do not match normal camera capture."
            )
        elif ai_prob <= 0.4:
            supports = SignalSupport.AUTHENTIC
            summary = "The spectral scan looks more like a real camera image than a generated one."
            what_found = (
                f"The model found fewer AI-like frequency artifacts than expected "
                f"({ai_prob:.0%} AI vs {auth_prob:.0%} authentic)."
            )
            why_it_matters = (
                "That slightly favors a real photo, because the hidden frequency structure looks more natural."
            )
        else:
            supports = SignalSupport.INCONCLUSIVE
            summary = "The spectral scan was mixed and did not clearly point one way."
            what_found = (
                f"The model saw some suspicious patterns, but not strongly enough to make this a clear call "
                f"({ai_prob:.0%} AI vs {auth_prob:.0%} authentic)."
            )
            why_it_matters = (
                "This means the hidden frequency patterns are ambiguous rather than clearly natural or clearly synthetic."
            )

        observations = [
            f"AI probability: {ai_prob:.3f}",
            f"Authentic probability: {auth_prob:.3f}",
        ]
        if load_error:
            observations.append(f"Model load notes: {load_error}")

        return EvidenceSignal(
            id=self.id,
            name=self.name,
            category=self.category,
            status=SignalStatus.OK,
            reliability=0.7,
            summary=summary,
            what_checked="We looked for hidden frequency and texture patterns that often show up in AI-generated images.",
            what_found=what_found,
            why_it_matters=why_it_matters,
            caveat="This signal is useful, but it should not decide the verdict on its own because editing, resizing, or new models can affect it.",
            observations=observations,
            metrics={"ai_probability": ai_prob, "auth_probability": auth_prob},
            confidence=max(ai_prob, auth_prob),
            supports=supports,
            notes="Spectral signal uses CNN + FFT fusion model.",
        )
