# DeepTrace Signal Library

DeepTrace analyzes images using multiple independent signals.  
Signals represent **evidence**, not conclusions.

Each signal contributes observations that help determine whether an image is likely authentic or AI-generated.

Signals must be interpretable and transparent.

---

# Signal Philosophy

No single detector should determine the final verdict.

Signals provide evidence that is later interpreted by the reasoning engine.

The system combines signals to form an overall forensic analysis.

---

# Signal Categories

The system currently focuses on several core signal types.

---

## Spectral Signals

Frequency-domain analysis of the image.

Purpose:
Detect generation artifacts created during diffusion or upsampling.

Examples:
- checkerboard artifacts
- periodic frequency peaks
- unusual frequency distributions

---

## Metadata & Provenance

Analysis of file-level information.

Examples:
- camera metadata
- EXIF fields
- editing traces
- missing or stripped metadata

Important:
Missing metadata alone does not imply AI generation.

---

## Noise & Sensor Patterns

Real cameras produce sensor noise patterns.

AI images often show:

- inconsistent noise
- overly smooth textures
- unnatural noise distribution

---

## Lighting & Physical Consistency

Evaluates whether lighting obeys physical rules.

Examples:
- inconsistent shadow direction
- incorrect reflections
- impossible illumination patterns

---

## Structural / Anatomical Signals

Detect anomalies in human anatomy or object structure.

Examples:
- warped hands
- distorted fingers
- inconsistent facial geometry
- unnatural accessory placement

---

## Semantic Inconsistencies

Logical inconsistencies in scenes.

Examples:
- repeated background structures
- impossible geometry
- inconsistent perspective
- text rendering anomalies

---

# Signal Evolution

DeepTrace must remain adaptable.

New signals can be added without changing the core reasoning system.

Future signals may include:

- diffusion fingerprint detection
- generative watermark detection
- adversarial artifact detection
- contextual verification signals