/**
 * MOCK / DEMO DATA FIXTURES FOR IDEA ENHANCER FRONTEND
 * 
 * IMPORTANT: These fixtures are strictly for standalone frontend demonstration
 * and testing without a running backend. They match the approved contract in
 * docs/API_CONTRACT.md exactly.
 * 
 * DO NOT treat these as live or verified results.
 * Placeholder external URLs are set to null so that unverified sources are not
 * presented as authentic project links.
 */

export const MOCK_SUCCESS_RESPONSE = {
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
};

export const MOCK_NO_MATCH_RESPONSE = {
  status: "success",
  query: "A quantum teleportation device for household pets using acoustic levitation",
  result_count: 0,
  matches: [],
  message: "No close match was found in the available dataset.",
  warnings: []
};

export const MOCK_VALIDATION_ERROR_RESPONSE = {
  status: "error",
  error_code: "VALIDATION_ERROR",
  message: "The 'idea' field must contain at least 10 characters.",
  details: {
    field: "idea",
    constraint: "min_length",
    min_length: 10,
    actual_length: 5
  }
};

export const MOCK_SERVER_ERROR_RESPONSE = {
  status: "error",
  error_code: "SEARCH_FAILED",
  message: "An internal error occurred while processing the search. Please try again.",
  details: null
};
