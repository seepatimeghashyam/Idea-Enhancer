# Idea Enhancer — POST /enhance API Contract

This document defines the formal request and response specification for the **Enhance** feature (`POST /enhance`). The frontend UI, API gateway, and backend services must adhere to this contract.

---

## Endpoint Overview

* **Route:** `POST /enhance`
* **Content-Type:** `application/json`
* **Purpose:** Takes a student's idea and top search matches (max 5) and generates a structured, evidence-grounded architectural enhancement analysis.
* **Strict Grounding Rule:** Every suggestion and overlap claim must cite one or more valid `project_id`s from the retrieved matches. If an LLM cites an unretrieved ID, it is dropped. Suggestions with zero valid citations are removed. If zero grounded suggestions remain, the request fails with `502 ENHANCE_BAD_LLM_OUTPUT`.

---

## 1. Request Schema

```json
{
  "idea": "An IoT-based crop disease detection system using Raspberry Pi and CNNs",
  "matches": [
    {
      "project_id": "rvce_042",
      "title": "Smart Crop Monitoring System",
      "description_excerpt": "A low-cost agricultural system monitoring crop health using sensor telemetry and CNN-based image classification.",
      "source_type": "institutional_project",
      "source_url": "https://example.com/record",
      "year": 2024,
      "domain": "IoT/Agriculture",
      "technologies": ["Raspberry Pi", "CNN", "Python"],
      "rank": 1,
      "bm25_rank": 1,
      "vector_rank": 3,
      "rrf_score": 0.0323,
      "shared_elements": ["Raspberry Pi", "CNN", "crop disease"],
      "verification_status": "checked"
    }
  ],
  "evidence_scope": "local"
}
```

### Request Fields

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `idea` | string | Yes | Min 10, max 2000 chars | The student's submitted project proposal. |
| `matches` | array of objects | No | Max 5 items | The retrieved match records from search. If no matches were found, pass `[]`. |
| `evidence_scope` | string | No | `"local"` or `"local+online"` (default: `"local"`) | Indicates the scope of the searched corpus. |

#### Match Object Constraints:
* `project_id`: string, min 1, max 128 chars (Required).
* `title`: string, min 1, max 300 chars (Required).
* `description_excerpt`: string, optional, max 2000 chars.
* `source_type`: string, optional, max 100 chars.
* `source_url`: string, optional, max 1000 chars.
* `domain`: string, optional, max 200 chars.
* `technologies`: array of strings, optional, max 20 items of max 60 chars.
* `shared_elements`: array of strings, optional, max 20 items of max 60 chars.
* `rank`: integer, optional (used for rank-aware sorting).
* `rrf_score`: number, optional.

---

## 2. Success Response Schema (`200 OK`)

```json
{
  "status": "success",
  "idea": "An IoT-based crop disease detection system using Raspberry Pi and CNNs",
  "overlap_summary": "Strong overlap found with existing IoT crop monitoring solutions, specifically regarding edge CNN inference on Raspberry Pi.",
  "facet_map": {
    "problem": {
      "overlap": "strong",
      "details": "Both focus on early identification of foliar crop diseases to minimize harvest loss.",
      "matched_project_ids": ["rvce_042"]
    },
    "domain": {
      "overlap": "strong",
      "details": "Precision agriculture and smart farming.",
      "matched_project_ids": ["rvce_042"]
    },
    "method": {
      "overlap": "partial",
      "details": "Both leverage Convolutional Neural Networks on edge devices, but the student proposal lacks multi-spectral imaging.",
      "matched_project_ids": ["rvce_042"]
    },
    "tech_stack": {
      "overlap": "strong",
      "details": "Direct overlap on Raspberry Pi, CNNs, and Python.",
      "matched_project_ids": ["rvce_042"]
    },
    "data": {
      "overlap": "partial",
      "details": "Relies on standard open leaf disease datasets (such as PlantVillage).",
      "matched_project_ids": ["rvce_042"]
    }
  },
  "novelty": {
    "level": "medium",
    "score": 0.48,
    "reason": "While the core edge-vision approach is well-explored in institutional archives, substantial novelty can be achieved by integrating lightweight quantization and offline mesh telemetry."
  },
  "suggestions": [
    {
      "title": "Edge INT8 Model Quantization & Hardware Acceleration",
      "description": "Quantize the CNN backbone using TensorFlow Lite or TensorRT to achieve 30+ FPS edge inference on low-power hardware, overcoming the latency bottleneck noted in rvce_042.",
      "cites": ["rvce_042"]
    },
    {
      "title": "LoRaWAN Mesh Telemetry for Offline Farm Environments",
      "description": "Incorporate long-range low-power radio communication to relay disease alerts where cellular connectivity is absent, expanding on the single-node setup in rvce_042.",
      "cites": ["rvce_042"]
    },
    {
      "title": "Multi-Modal Microclimate & Soil Sensor Fusion",
      "description": "Correlate visual leaf lesion detection with soil moisture and ambient humidity data to diagnose environmental root rot before visible foliar symptoms appear.",
      "cites": ["rvce_042"]
    }
  ],
  "suggested_tech_stack": [
    {
      "name": "TensorFlow Lite / Edge TPU",
      "role": "Low-power INT8 quantized edge inference"
    },
    {
      "name": "LoRa SX1276 / ESP32",
      "role": "Long-range mesh communication in rural areas"
    },
    {
      "name": "FastAPI + TimescaleDB",
      "role": "Time-series sensor data ingestion and analysis"
    }
  ],
  "feasibility": {
    "rating": 4,
    "reasons": [
      "Hardware components (Raspberry Pi, camera modules, sensors) are accessible and student-budget friendly.",
      "Pretrained vision models (MobileNetV3, YOLOv8-nano) offer high accuracy transfer learning with minimal initial training cost."
    ]
  },
  "cached": false,
  "warnings": []
}
```

### Novelty Representation

* When matches are present, `novelty.score` is a float between `0.05` and `0.95`, and `novelty.level` is `"low"`, `"medium"`, or `"high"`.
* When **zero matches** are present:
  * `novelty.level` is `"unknown"`.
  * `novelty.score` is `null`.
  * `novelty.reason` clearly explains that a missing local match is not proof of novelty and that a wider search is needed.

### Grounding Rules
* If fewer than 3 valid suggestions remain after filtering ungrounded citations, the valid ones (1–2) are returned, and `warnings` contains `["Fewer than 3 grounded suggestions were produced."]`.
* If a facet claims `"partial"` or `"strong"` overlap without citing any valid retrieved IDs, its overlap is automatically downgraded to `"none"` with `matched_project_ids: []`.
* Invalid citations are never forged or replaced by the top match ID.

---

## 3. Error Responses

### 3.1 Bad LLM Output (`502 Bad Gateway`)

Returned when the AI returns invalid JSON, missing required fields, or zero grounded suggestions:

```json
{
  "status": "error",
  "error_code": "ENHANCE_BAD_LLM_OUTPUT",
  "message": "The AI returned an unusable answer. Please try again.",
  "details": null
}
```

### 3.2 Validation Error (`422 Unprocessable Entity`)

Returned when request violates constraints (e.g. idea too short, more than 5 matches, oversized fields):

```json
{
  "status": "error",
  "error_code": "VALIDATION_ERROR",
  "message": "The request body must be a valid JSON object.",
  "details": [...]
}
```

### 3.3 LLM Service Unavailable / Timeout (`503 Service Unavailable`)

```json
{
  "status": "error",
  "error_code": "LLM_TIMEOUT",
  "message": "The AI enhancement service timed out while generating suggestions. Please try again.",
  "details": null
}
```
