# Proposed Query Evidence Review

**Status:** Proposed for human approval; not yet added to `queries.example.json`.

**Purpose:** Provide source-backed, realistic engineering project-query candidates for the human relevance benchmark. Each source demonstrates that a closely related implementation, prototype, or research workflow exists. It does **not** establish that the proposed query is novel, independently validated, safe for deployment, or representative of the user's college.

## Review rules

- Keep each query as a problem statement, not as a claim that the proposed system already works.
- The linked repository/paper is evidence of a related project area only. Reviewers should inspect the source before accepting the query.
- Do not copy a source project's description or technology stack into the dataset as verified metadata without checking its own evidence and reuse terms.
- These candidates were selected to avoid close duplication of the existing 15 queries in `data/evaluation/queries.example.json`. A human should still check overlap and confirm that the relevant departments exist at the user's college.
- Query acceptance is separate from candidate relevance grading. No candidate records or relevance labels are included here.

## Proposed candidates

### 1. Structural crack and corrosion inspection
- **query_id:** `structural-defect-vision`
- **slice:** `civil_structural_health`
- **tags:** `civil`, `computer vision`, `crack detection`, `corrosion`
- **query:** Build an image-based inspection tool that detects visible cracks and corrosion on concrete or steel structures, tracks defect locations across inspection images, and produces a review report for an engineer.
- **Evidence:** https://github.com/1225zisu-lab/Structural-Health-Monitoring
- **Evidence scope:** Repository describes crack/corrosion detection in images and video, tracking, severity estimates, and report generation. It also cites DOI 10.5281/zenodo.17583551.
- **Caveat:** Treat its reported capabilities as claims in the repository; do not assume field-grade structural assessment.

### 2. Bridge vibration and load monitoring
- **query_id:** `bridge-vibration-monitor`
- **slice:** `civil_iot_monitoring`
- **tags:** `civil`, `structural monitoring`, `vibration`, `sensors`
- **query:** Prototype a tabletop bridge-monitoring system that records vibration and support loads under controlled test conditions and flags changes that may indicate a change in structural behaviour.
- **Evidence:** https://github.com/pranav-atreya/structural-health-iot-analytics
- **Evidence scope:** Repository describes an instrumented tabletop bridge with vibration, load-cell, and vehicle-crossing measurements.
- **Caveat:** A tabletop demonstrator is not evidence of suitability for real bridges.

### 3. CNC cutting-tool wear estimation
- **query_id:** `cnc-tool-wear-estimator`
- **slice:** `mechanical_manufacturing`
- **tags:** `mechanical`, `CNC`, `tool wear`, `machine learning`
- **query:** Develop a model that estimates CNC cutting-tool wear from machining sensor signals and provides an early warning for inspection or tool replacement.
- **Evidence:** https://github.com/VB-Builds/tool-wear-detector
- **Evidence scope:** Repository describes wear estimation and remaining-life prediction using spindle load, vibration, acoustic emission, and a NASA milling-wear dataset.
- **Caveat:** Check the dataset protocol and held-out-cutter evaluation; do not assume reported performance generalizes to other machines.

### 4. 3D-printer failure detection
- **query_id:** `fdm-print-failure-detection`
- **slice:** `mechanical_computer_vision`
- **tags:** `mechanical`, `3D printing`, `computer vision`, `edge AI`
- **query:** Create a camera-based monitor that detects common FDM printing failures, such as spaghetti-like extrusion or layer shifts, and alerts the operator before a long print is wasted.
- **Evidence:** https://github.com/SebTC/FDM-Failure-Detection
- **Evidence scope:** Repository describes real-time camera-based failure detection and printer pause/notification integration.
- **Caveat:** Verify the test data and hardware conditions; the reported metrics are repository-reported, not independently audited here.

### 5. Vision-guided pick-and-place robot
- **query_id:** `vision-guided-pick-place`
- **slice:** `robotics_automation`
- **tags:** `robotics`, `computer vision`, `kinematics`, `embedded`
- **query:** Build a small robotic arm that identifies selected objects with a camera, estimates their positions, and performs a pick-and-place task with repeatable motion.
- **Evidence:** https://github.com/xfreakybob/computer-vision-robot-arm
- **Evidence scope:** Repository describes a camera-guided four-degree-of-freedom arm using object detection, inverse kinematics, and servo control.
- **Caveat:** A tabletop demonstration does not establish industrial accuracy or safe human-robot collaboration.

### 6. Conveyor-based object sorting
- **query_id:** `conveyor-object-sorter`
- **slice:** `robotics_mechatronics`
- **tags:** `robotics`, `mechatronics`, `conveyor`, `sorting`
- **query:** Prototype a conveyor and robotic-arm system that classifies objects by a measurable property such as size and routes each object to the corresponding collection area.
- **Evidence:** https://github.com/jewel-nath/conveysort-arm
- **Evidence scope:** Repository describes a conveyor and six-servo arm sorting blocks by size using camera measurements and Arduino control; it references a Zenodo project record.
- **Caveat:** The repository distinguishes implemented sorting behaviour from a separately written ROS 2 workspace; preserve that distinction.

### 7. Automated waste segregation
- **query_id:** `vision-waste-segregation`
- **slice:** `environmental_automation`
- **tags:** `environmental`, `AI`, `waste sorting`, `actuators`
- **query:** Build a small sorting prototype that classifies a limited set of common waste categories from images and uses actuators to direct items into separate bins.
- **Evidence:** https://github.com/mscsAhsan/smart-bin
- **Evidence scope:** Repository describes a conveyor-based image-classification and servo-routing prototype and reports separate classifier and physical sorting results.
- **Caveat:** Physical sorting performance is distinct from image-classifier accuracy; test mixed, dirty, and partially occluded items.

### 8. Offline indoor air-quality monitor
- **query_id:** `offline-indoor-air-monitor`
- **slice:** `electronics_environmental_sensing`
- **tags:** `ECE`, `embedded systems`, `air quality`, `offline`
- **query:** Develop an offline-capable indoor monitor that records carbon-dioxide, temperature, and humidity readings locally and provides a local dashboard without requiring cloud connectivity.
- **Evidence:** https://github.com/bragesom/esp32-air-quality-monitor
- **Evidence scope:** Repository describes an ESP32/SCD30 monitor with local CSV logging, display, and a self-hosted web interface.
- **Caveat:** Sensor calibration and the distinction between true CO2 sensors and estimated-CO2 gas sensors must be checked.

### 9. Dual-axis solar tracking and output comparison
- **query_id:** `dual-axis-solar-tracker`
- **slice:** `eee_renewable_energy`
- **tags:** `EEE`, `renewable energy`, `control systems`, `solar`
- **query:** Design a dual-axis solar-panel tracker and compare its measured electrical energy output against a fixed-panel baseline under the same test conditions.
- **Evidence:** https://github.com/ldad64/solar-tracker
- **Evidence scope:** Repository describes dual-axis tracking, servo control, voltage/current/power measurement, and energy accumulation.
- **Caveat:** A tracker moving toward a light source does not by itself prove a net energy gain; the comparison needs controlled measurements and actuator-power accounting.

### 10. EMG-controlled prosthetic hand with tactile feedback
- **query_id:** `emg-prosthetic-haptic-feedback`
- **slice:** `biomedical_mechatronics`
- **tags:** `biomedical`, `EMG`, `prosthetics`, `haptics`
- **query:** Prototype a low-cost hand mechanism controlled by surface muscle signals and provide simple vibration feedback based on fingertip force measurements.
- **Evidence:** https://github.com/sofiabolt/sensory-tactile-emg-prosthesis-synapsebio
- **Evidence scope:** Repository describes Arduino-based EMG control, fingertip pressure sensing, and vibrotactile feedback.
- **Caveat:** This is a research/educational prototype idea, not a clinically validated or patient-ready prosthesis; involve appropriate supervision and consent for any human testing.

### 11. Safety helmet with fall detection and location alert
- **query_id:** `safety-helmet-fall-alert`
- **slice:** `ece_worker_safety`
- **tags:** `ECE`, `embedded`, `wearable`, `safety`
- **query:** Build a wearable helmet prototype that detects a possible severe impact, allows the wearer to cancel a false alarm, and sends an emergency notification with location when connectivity is available.
- **Evidence:** https://github.com/zykonemeziz/Smart_Helmet
- **Evidence scope:** Repository describes ESP32-based fall detection, GPS, GSM/SMS notification, and a cancel button.
- **Caveat:** Threshold-based impact detection can produce false positives/negatives; this must not be presented as a certified safety device.

### 12. Camera-assisted parking occupancy estimation
- **query_id:** `camera-parking-occupancy`
- **slice:** `computer_vision_smart_infrastructure`
- **tags:** `computer vision`, `smart infrastructure`, `parking`, `IoT`
- **query:** Create a parking-area monitor that estimates occupied and free spaces from periodic camera images and displays the current availability without retaining unnecessary identifiable footage.
- **Evidence:** https://github.com/AJC938/smart-parking-yolo
- **Evidence scope:** The README describes a local parking-lot video application using YOLO vehicle detection, ByteTrack tracking, mapped parking spaces, and a dashboard showing occupied and available spaces.
- **Caveat:** This is a video-based demonstrator; test changes in camera angle, lighting, occlusion, and privacy before claiming live-site reliability.

### 13. Plant-leaf disease-region segmentation
- **query_id:** `leaf-disease-severity-segmentation`
- **slice:** `ai_agri_computer_vision`
- **tags:** `AI`, `agriculture`, `image segmentation`, `plant health`
- **query:** Develop a tool that segments visibly affected regions in leaf images and estimates the affected image area to support agricultural inspection.
- **Evidence:** https://github.com/smoothoperator20/leaf-disease-detection
- **Evidence scope:** Repository describes U-Net/DeepLabV3+ segmentation, model comparison, and pixel-area-based severity estimation.
- **Caveat:** Image-area estimates are not a validated agronomic diagnosis; performance on field images must be tested separately.

### 14. EV charging schedule under a power limit
- **query_id:** `ev-charging-load-scheduler`
- **slice:** `electrical_energy_optimization`
- **tags:** `EEE`, `EV charging`, `optimization`, `simulation`
- **query:** Build a simulator that schedules electric-vehicle charging sessions under a limited site power capacity while comparing waiting time, energy cost, and peak demand.
- **Evidence:** https://github.com/suhasmreddy/ev-depot-optimizer
- **Evidence scope:** Repository describes constrained optimization and discrete-event simulation for commercial EV charging under transformer limits and uncertain arrivals.
- **Caveat:** Its vehicle and operating conditions are synthetic; this supports a simulation project, not a claim of field deployment.

### 15. Lithium-ion battery state-of-health estimation
- **query_id:** `lithium-battery-health-estimation`
- **slice:** `eee_battery_analytics`
- **tags:** `EEE`, `battery`, `machine learning`, `state of health`
- **query:** Develop and evaluate a model that estimates lithium-ion battery state of health from cycling or discharge measurements, using chronological train/test splits to test future-cycle prediction.
- **Evidence:** https://github.com/adicyb/battery-soh-prediction
- **Evidence scope:** Repository describes state-of-health estimation using NASA PCoE battery data and reports both chronological and random-split results.
- **Caveat:** The repository itself illustrates why random splits can overstate future-cycle performance; use chronological evaluation and report limitations.

## Recommended next steps

1. A team member checks that these topics fit the actual college departments and are not duplicates of the existing query set.
2. A human reviewer approves, edits, or rejects each proposed query.
3. Only approved query objects are added to a new version of the query catalogue. Do not overwrite the existing v1 catalogue silently.
4. Capture a fresh immutable provider snapshot using the approved catalogue.
5. Human reviewers grade every captured candidate; this evidence review does not contain relevance labels.


## Source-check log — 2026-11-26

The linked GitHub repositories were checked for public repository availability and their README contents were inspected to confirm that the described project area is present. The parking-occupancy source was replaced after the initially listed repository returned not found during the check; the current source is `AJC938/smart-parking-yolo`.

**What this check verifies:** the public repositories exist and their README text describes a project relevant to the corresponding query.

**What this check does not verify:** independent reproduction of results, hardware performance, dataset rights/quality, peer review, safety, deployment readiness, or novelty. Performance numbers and implementation claims remain repository-author claims unless separately reproduced or independently published.
