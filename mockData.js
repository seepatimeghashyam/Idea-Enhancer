/**
 * MOCK / DEMO DATA FIXTURES FOR IDEA ENHANCER FRONTEND
 *
 * IMPORTANT: These fixtures are strictly for standalone frontend demonstration
 * and testing without a running backend. Their shapes follow the approved
 * POST /search contract (docs/API_CONTRACT.md).
 *
 * DO NOT treat these as live or verified results. They are FIXED sample
 * payloads: they do NOT depend on the idea the user types, and the UI must
 * always label them as demo data. Placeholder external URLs are null so that
 * unverified sources are never presented as authentic project links.
 *
 * Fixtures are deep-frozen; consumers must call cloneFixture() before
 * adapting a payload (e.g. truncating to top_k) so the originals never change.
 */

function deepFreeze(value) {
  if (value && typeof value === 'object' && !Object.isFrozen(value)) {
    Object.freeze(value);
    Object.values(value).forEach(deepFreeze);
  }
  return value;
}

/** Return a mutable deep copy of a fixture payload. */
export function cloneFixture(fixture) {
  return JSON.parse(JSON.stringify(fixture));
}

/**
 * Illustrative fixtures only: neutral IDs/types, no URLs, and explicitly unchecked.
 * They preview the response shape and do not claim real project provenance.
 */
const DEMO_RECORDS = [
  ["Smart Crop Monitoring System", "IoT / Agriculture", ["Raspberry Pi", "CNN", "Python"], ["crop monitoring", "CNN", "leaf disease"]],
  ["Plant Disease Detection Using Deep Learning", "AI / Agriculture", ["CNN", "TensorFlow", "OpenCV"], ["disease detection", "CNN"]],
  ["Greenhouse Climate Controller", "IoT / Agriculture", ["ESP32", "MQTT"], ["sensors", "monitoring"]],
  ["Leaf Image Classifier on a Phone", "Mobile / Computer Vision", ["Kotlin", "TensorFlow Lite"], ["leaf", "classification"]],
  ["Soil Moisture Alert Network", "IoT / Environment", ["LoRa", "Arduino"], ["sensor network"]],
  ["Drone-Based Field Survey", "Robotics / Agriculture", ["Python", "OpenCV"], ["field imaging"]],
  ["Crop Yield Forecasting Dashboard", "Data Science", ["Python", "scikit-learn"], ["yield", "forecasting"]],
  ["Pest Trap Image Counter", "Computer Vision", ["YOLO", "Python"], ["image detection"]],
  ["Farm Weather Station", "Embedded Systems", ["STM32", "C"], ["environment sensing"]],
  ["Irrigation Scheduler", "IoT / Agriculture", ["Python", "Raspberry Pi"], ["Raspberry Pi", "irrigation"]],
  ["Edge Inference for Camera Traps", "Edge Computing", ["TensorFlow Lite"], ["edge inference"]],
  ["Fruit Ripeness Estimator", "Computer Vision", ["PyTorch"], ["image classification"]],
  ["Livestock Activity Tracker", "IoT / Wearables", ["BLE", "C++"], ["activity sensing"]],
  ["Rural Advisory Chatbot", "NLP / Social Good", ["Python", "Rasa"], ["advisory"]],
  ["Hydroponic Nutrient Monitor", "IoT / Agriculture", ["Arduino", "Python"], ["nutrient sensing"]],
  ["Satellite NDVI Explorer", "Remote Sensing", ["Python", "GDAL"], ["vegetation index"]],
  ["Low-Power Image Sensor Node", "Embedded Systems", ["ESP32-CAM"], ["low power", "camera"]],
  ["Farmer Market Price Tracker", "Data Science", ["JavaScript"], ["price data"]],
  ["Disease Outbreak Heat Map", "Data Visualisation", ["D3.js"], ["disease", "mapping"]],
  ["Solar-Powered Field Logger", "Embedded Systems", ["C", "LoRa"], ["solar", "logging"]]
].map(([title, domain, technologies, shared], index) => ({
  project_id: `demo_${String(index + 1).padStart(2, "0")}`,
  title,
  description_excerpt: "Illustrative sample text used only to show a result card. It does not describe a real project.",
  source_type: "demo_record",
  source_url: null,
  year: 2020 + (index % 6),
  domain,
  technologies,
  rank: index + 1,
  bm25_rank: null,
  vector_rank: null,
  rrf_score: 0,
  shared_elements: shared,
  verification_status: "unchecked"
}));

/** Build a demo payload with a match count that respects the requested limit. */
export function buildMockSuccess(topK) {
  const n = Number.isInteger(topK) ? Math.min(Math.max(topK, 1), DEMO_RECORDS.length) : 5;
  const matches = DEMO_RECORDS.slice(0, n).map((record) => ({
    ...record,
    technologies: [...record.technologies],
    shared_elements: [...record.shared_elements]
  }));
  return {
    status: "success",
    query: "An IoT-based crop disease detection system using Raspberry Pi and CNNs",
    result_count: matches.length,
    matches,
    message: null,
    warnings: []
  };
}

export const MOCK_SUCCESS_RESPONSE = deepFreeze(buildMockSuccess(5));

export const MOCK_NO_MATCH_RESPONSE = deepFreeze({
  status: "success",
  query: "A quantum teleportation device for household pets using acoustic levitation",
  result_count: 0,
  matches: [],
  message: "No close match was found in the available dataset.",
  warnings: []
});

export const MOCK_VALIDATION_ERROR_RESPONSE = deepFreeze({
  status: "error",
  error_code: "VALIDATION_ERROR",
  message: "Demo scenario: simulated server-side validation error. This is a demonstration and does not indicate a problem with your submitted idea.",
  details: {
    field: "idea",
    constraint: "min_length",
    min_length: 10
  }
});

export const MOCK_SERVER_ERROR_RESPONSE = deepFreeze({
  status: "error",
  error_code: "SEARCH_FAILED",
  message: "Demo scenario: simulated server error. Nothing is actually wrong.",
  details: null
});

/**
 * Scenario registry used by the UI mode selector.
 * kind "success" resolves with the payload; kind "error" rejects with the
 * given HTTP status and payload (mirroring the real API's error envelope).
 */
export const MOCK_SCENARIOS = Object.freeze({
  'mock-success':      Object.freeze({ kind: 'success', delay: 600, payload: MOCK_SUCCESS_RESPONSE, build: buildMockSuccess }),
  'mock-no-match':     Object.freeze({ kind: 'success', delay: 600, payload: MOCK_NO_MATCH_RESPONSE }),
  'mock-val-error':    Object.freeze({ kind: 'error', status: 422, delay: 400, payload: MOCK_VALIDATION_ERROR_RESPONSE }),
  'mock-server-error': Object.freeze({ kind: 'error', status: 500, delay: 400, payload: MOCK_SERVER_ERROR_RESPONSE })
});
