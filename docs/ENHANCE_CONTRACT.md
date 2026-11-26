# Idea Enhancer — POST /enhance API Contract

This document defines the formal request and response specification for the **Enhance** feature (`POST /enhance`). The frontend UI, API gateway, and backend services must adhere to this contract.

---

## Endpoint Overview

* **Route:** `POST /enhance`
* **Content-Type:** `application/json`
* **Purpose:** Takes a student's idea and the retrieved top matches (from `POST /search` or `/live-search`) and generates a structured, evidence-grounded architectural enhancement analysis.
* **Grounding Rule:** Every suggestion and overlap claim must cite one or more `project_id`s from the retrieved search matches. The LLM is strictly prohibited from inventing projects or citing non-retrieved IDs.

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
  ]
}
```

### Request Fields

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `idea` | string | Yes | Min 10, max 2000 chars | The student's submitted project proposal. |
| `matches` | array of objects | Yes | Max 20 items | The retrieved match records from `POST /search`. If no matches were found, pass an empty array `[]`. |

Each object in `matches` must include at least:
* `project_id` (string, required)
* `title` (string, required)
* `description_excerpt` (string, optional)
* `domain` (string, optional)
* `technologies` (array of strings, optional)
* `rrf_score` (number, optional)
* `shared_elements` (array of strings, optional)

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
      "Pretrained vision models (MobileNetV3, YOLOv8-nano) offer high accuracy transfer learning with minimal initial training cost.",
      "Field calibration and multi-modal sensor fusion will require moderate engineering effort and testing."
    ]
  },
  "cached": false
}
```

### Response Field Definitions

* **`status`**: `"success"`
* **`idea`**: Echo of the student's idea string.
* **`overlap_summary`**: 1–2 sentence high-level synthesis of how the idea compares with the retrieved corpus.
* **`facet_map`**: Analysis across 5 dimensions:
  * `problem`: Target problem and use-case overlap.
  * `domain`: Industry / application sector overlap.
  * `method`: Algorithmic and architectural methodology overlap.
  * `tech_stack`: Overlap of libraries, hardware, and frameworks.
  * `data`: Datasets, telemetry, and input format overlap.
  * Each facet contains:
    * `overlap`: `"none"` | `"partial"` | `"strong"`
    * `details`: Explanatory reasoning.
    * `matched_project_ids`: List of cited project IDs from the request matches.
* **`novelty`**:
  * `level`: `"low"` | `"medium"` | `"high"` (Derived directly from the evidence-based score).
  * `score`: Float between `0.00` and `1.00` (computed deterministically from match overlap, RRF scores, and shared elements).
  * `reason`: Clear explanation of the novelty rating grounded in evidence.
* **`suggestions`**: Array of 3–5 actionable improvements.
  * Every suggestion **must** cite at least one `project_id` from the retrieved matches (`cites: ["<id>"]`).
  * If `matches` was empty, `cites` will be empty (`[]`).
* **`suggested_tech_stack`**: Array of 3–6 recommended tools/technologies with their specific role.
* **`feasibility`**:
  * `rating`: Integer from `1` (Extremely difficult / unrealistic for students) to `5` (Highly feasible with standard student resources).
  * `reasons`: 2–4 concise bullet points explaining the rating.
* **`cached`**: Boolean indicating whether the result was served from the in-memory cache.

---

## 3. Error Responses

All error responses use the standard envelope defined in `docs/API_CONTRACT.md`.

### 3.1 Validation Error (`422 Unprocessable Entity`)

Returned when `idea` is too short/long, `matches` is invalid, or required fields are missing:

```json
{
  "status": "error",
  "error_code": "VALIDATION_ERROR",
  "message": "The 'idea' field must contain at least 10 characters.",
  "details": {
    "field": "idea",
    "constraint": "min_length",
    "min_length": 10,
    "actual_length": 4
  }
}
```

### 3.2 LLM Service Unavailable / Timeout (`503 Service Unavailable`)

Returned when the LLM provider fails, times out, rate limits, or API key is unconfigured:

```json
{
  "status": "error",
  "error_code": "LLM_UNAVAILABLE",
  "message": "The AI enhancement service is currently unavailable or timed out. Please try again.",
  "details": null
}
```

### 3.3 Internal Error (`500 Internal Server Error`)

```json
{
  "status": "error",
  "error_code": "ENHANCE_FAILED",
  "message": "An unexpected error occurred while generating enhancements.",
  "details": null
}
```
