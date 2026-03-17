# DeepTrace Evidence Schema

This schema defines the structured evidence produced by detectors and consumed by the reasoning layer.

## EvidenceSignal

- `id`: Stable identifier for the detector (string).
- `name`: Human-readable signal name (string).
- `category`: Signal category (string).
- `status`: One of `ok`, `warning`, `unavailable`, `error`.
- `reliability`: Estimated reliability between `0.0` and `1.0`.
- `summary`: Short summary of what the signal observed.
- `observations`: List of specific observations (strings).
- `metrics`: Structured numeric or categorical measurements (object).
- `confidence`: Optional detector confidence between `0.0` and `1.0`.
- `supports`: One of `authentic`, `ai_generated`, `inconclusive`, `unknown`.
- `notes`: Optional contextual notes or caveats.

## EvidenceProfile

- `image`: Image metadata.
- `signals`: List of `EvidenceSignal`.
- `warnings`: System-level warnings.

## ImageInfo

- `width`: Image width in pixels.
- `height`: Image height in pixels.
- `mode`: Image color mode.
- `sha256`: SHA-256 hash of the image bytes.
- `format`: Optional image format.

## Example EvidenceSignal

```json
{
  "id": "metadata_analysis",
  "name": "Metadata & Provenance",
  "category": "metadata",
  "status": "ok",
  "reliability": 0.35,
  "summary": "Metadata review completed.",
  "observations": [
    "Camera make: Canon",
    "Camera model: EOS R5"
  ],
  "metrics": {
    "exif_count": 24
  },
  "confidence": null,
  "supports": "authentic",
  "notes": "Missing metadata alone does not imply AI generation."
}
```
