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

export const MOCK_SUCCESS_RESPONSE = deepFreeze({
  status: "success",
  query: "An IoT-based crop disease detection system using Raspberry Pi and CNNs",
  result_count: 2,
  matches: [
    {
      project_id: "rvce_042",
      title: "Smart Crop Monitoring System",
      description_excerpt: "Monitors environmental factors and visual crop symptoms to identify early-stage leaf blight using convolutional neural networks on embedded edge hardware.",
      source_type: "rvce",
      source_url: null,
      year: 2024,
      domain: "IoT/Agriculture",
      technologies: ["Raspberry Pi", "CNN", "Python", "TensorFlow Lite"],
      rank: 1,
      bm25_rank: 1,
      vector_rank: 3,
      rrf_score: 0.0323,
      shared_elements: ["Raspberry Pi", "crop monitoring", "CNN", "leaf disease"],
      verification_status: "checked"
    },
    {
      project_id: "global_107",
      title: "Plant Disease Detection Using Deep Learning",
      description_excerpt: "An automated classification pipeline trained on open plant pathology datasets to detect foliar diseases from mobile camera captures.",
      source_type: "global",
      source_url: null,
      year: 2023,
      domain: "AI/Agriculture",
      technologies: ["CNN", "TensorFlow", "Python", "OpenCV"],
      rank: 2,
      bm25_rank: 4,
      vector_rank: 1,
      rrf_score: 0.0298,
      shared_elements: ["disease detection", "CNN", "deep learning"],
      verification_status: "checked"
    }
  ],
  message: null,
  warnings: []
});

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
  message: "An internal error occurred while processing the search. Please try again.",
  details: null
});

/**
 * Scenario registry used by the UI mode selector.
 * kind "success" resolves with the payload; kind "error" rejects with the
 * given HTTP status and payload (mirroring the real API's error envelope).
 */
export const MOCK_SCENARIOS = Object.freeze({
  'mock-success':      Object.freeze({ kind: 'success', delay: 600, payload: MOCK_SUCCESS_RESPONSE }),
  'mock-no-match':     Object.freeze({ kind: 'success', delay: 600, payload: MOCK_NO_MATCH_RESPONSE }),
  'mock-val-error':    Object.freeze({ kind: 'error', status: 422, delay: 400, payload: MOCK_VALIDATION_ERROR_RESPONSE }),
  'mock-server-error': Object.freeze({ kind: 'error', status: 500, delay: 400, payload: MOCK_SERVER_ERROR_RESPONSE })
});
