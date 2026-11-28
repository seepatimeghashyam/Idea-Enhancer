#!/usr/bin/env python3
"""Generate synthetic abstracts for placeholder records based on title and domain."""

from __future__ import annotations

import csv
import re
from pathlib import Path

DATASET_PATH = Path("data/historical_projects.csv")
OUTPUT_PATH = Path("data/historical_projects_enriched.csv")

# Domain-specific abstract templates
DOMAIN_TEMPLATES = {
    "Healthcare / AI": "This project develops an AI-driven healthcare solution for {topic}. The system leverages machine learning algorithms to {action} with improved accuracy and efficiency compared to traditional methods. Experimental results demonstrate promising performance in clinical validation.",
    "Assistive Technology / Computer Vision": "This assistive technology project creates a computer vision system to help visually impaired users {action}. The system uses {tech} for real-time {task}, providing audio/haptic feedback for enhanced accessibility.",
    "Environmental IoT / AI": "This environmental monitoring system combines IoT sensors with AI analytics to {action}. The deployed sensor network collects {data_type} data which is processed using machine learning models for {prediction_task}. Field trials show reliable operation.",
    "Public Safety / Computer Vision": "This public safety system employs computer vision to {action} in {setting}. Using {tech}, the system detects {target} with high accuracy and alerts authorities in real-time. Privacy-preserving design ensures data protection.",
    "Cybersecurity / Media Forensics": "This cybersecurity tool detects {threat} in digital media using {tech}. The system analyzes {features} to identify manipulation with {accuracy}% accuracy. Applications include misinformation detection and digital evidence verification.",
    "Extended Reality / Education": "This XR educational platform creates immersive learning experiences for {subject}. Using {tech}, students can {action} in virtual environments. User studies show improved engagement and learning outcomes.",
    "Cybersecurity / Software Defined Networking": "This SDN security solution implements {tech} for network anomaly detection. The system monitors {traffic_type} traffic and applies {ml_method} to identify threats with low false positive rates.",
    "Virtual Reality / Aerospace Simulation": "This VR simulation provides realistic aerospace maintenance training. Technicians can {action} in a virtual hangar using {tech}. The system reduces training costs by {percentage}% while maintaining skill transfer.",
    "Environmental AI / Geospatial Modeling": "This geospatial AI system analyzes {data_source} to {action}. Using {ml_method} on satellite imagery, the model predicts {target} with high spatial resolution. Results support urban planning decisions.",
    "Hardware Security / VLSI Systems": "This hardware security implementation uses {tech} for {security_function}. The {algorithm} architecture provides {security_property} with minimal area/power overhead. Implemented on {platform} with {frequency}MHz operation.",
    "Natural Language Processing / Information Systems": "This NLP system processes {document_type} using {tech}. The pipeline includes {preprocessing} followed by {model} for {task}. Evaluation on {dataset} shows state-of-the-art performance.",
    "IoT / Embedded Vision": "This embedded vision system runs on {hardware} for {application}. Using {model} optimized for edge deployment, the system achieves {fps} FPS with {accuracy}% accuracy. Power consumption is {power}mW.",
    "Smart Agriculture / Aquaculture IoT": "This aquaculture monitoring system uses {sensors} to measure {parameters}. Data is transmitted via {protocol} to {cloud/edge} for {analysis}. Farmers receive real-time alerts for {conditions}.",
    "Computer Vision / Video Analytics": "This video analytics platform uses {model} for {task}. The spatiotemporal architecture captures {features} for accurate {detection}. Tested on {dataset} with {metrics}.",
    "Cybersecurity / Network Defense": "This network defense system analyzes {traffic} using {ml_method}. The ensemble approach combines {models} for robust {threat} detection. Deployed in {environment} with {performance} results.",
    "Data Science / Graph Machine Learning": "This graph neural network models {entities} for {task}. Using {gnn_type} with {layers} layers, the model captures {order}-order interactions. Outperforms baselines on {benchmarks}.",
    "Healthcare AI / Pharmaceutical Vision": "This pharmaceutical inspection system uses {model} for {task}. The vision pipeline processes {image_type} at {speed} with {accuracy}%. FDA-compliant design ensures regulatory compliance.",
    "Conversational AI / Edge Computing": "This edge conversational assistant runs {model} locally on {hardware}. Using quantization and {optimization}, the system achieves {latency}ms response with {memory}MB footprint. Privacy-preserving by design.",
    "Computer Vision / Deep Learning": "This deep learning system applies {architecture} for {task}. The model uses {technique} for improved {metric}. Trained on {dataset} with {augmentation}, achieving {results}.",
    "Blockchain / Decentralized Systems": "This blockchain system implements {consensus} for {application}. Smart contracts in {language} enable {functionality}. Gas optimization reduces costs by {percentage}%.",
    "Power Systems / Renewable Energy": "This renewable energy system optimizes {component} using {algorithm}. The {topology} achieves {efficiency}% efficiency under {conditions}. Hardware validation confirms theoretical predictions.",
    "IoT / Embedded Systems": "This embedded IoT device uses {mcu} for {application}. The {protocol} communication enables {connectivity}. Power management achieves {battery_life} on {battery_type}.",
    "Materials Science & Mechanical Systems": "This mechanical system analyzes {structure} using {simulation}. {method} reveals {insight} about {phenomenon}. Experimental validation matches simulation within {error}%.",
    "Applied Engineering / Computing": "This computing system implements {algorithm} for {problem}. The {architecture} achieves {speedup}x speedup over {baseline}. Resource utilization optimized for {constraint}.",
    "Robotics / Autonomous Systems": "This autonomous robot uses {sensors} for {navigation}. The {algorithm} planner generates {trajectory_type} paths in {time}. Field tests in {environment} demonstrate robustness.",
    "VLSI Design / Microelectronics": "This VLSI design implements {function} in {process}nm. The {architecture} achieves {frequency}GHz at {power}mW. Layout verified with {signoff_tools}.",
    "Cloud Computing / Distributed Systems": "This distributed system uses {framework} for {workload}. The {consistency} model ensures {guarantees} while maintaining {performance}. Scales to {nodes} nodes.",
    "Natural Language Processing / AI": "This NLP system processes {language} for {task}. Using {model} with {parameters} parameters, it achieves {score} on {benchmark}. Fine-tuned for {domain}.",
    "Computer Vision / Deep Learning": "This vision system uses {architecture} for {task}. The {technique} improves {metric} by {percentage}%. Trained with {data} images using {augmentation}.",
    "Applied Engineering / Computing": "This engineering system applies {method} to solve {problem}. The {implementation} achieves {performance} on {hardware}. Validated through {testing}.",
    "Healthcare Technology / Biomedical Engineering": "This biomedical system monitors {physiological_signal} for {condition}. The {sensor_type} sensor provides {resolution} with {comfort}. Clinical validation shows {accuracy}% correlation.",
}

# Generic fallback
GENERIC_TEMPLATE = "This engineering project develops a {domain} system for {topic}. Using {tech}, the system {action} with improved {metric} over existing approaches. The implementation leverages {method} and has been validated through {validation}."

# Technology keywords extracted from titles
TITLE_TECH_PATTERNS = {
    r"\b(?:cnn|convolutional neural network)\b": "CNNs",
    r"\b(?:rnn|recurrent neural network|lstm|gru)\b": "RNNs/LSTMs",
    r"\b(?:transformer|bert|gpt)\b": "transformer models",
    r"\b(?:yolo|object detection)\b": "YOLO",
    r"\b(?:esp32|esp8266)\b": "ESP32/ESP8266 microcontrollers",
    r"\b(?:raspberry pi|rpi)\b": "Raspberry Pi",
    r"\b(?:arduino)\b": "Arduino",
    r"\b(?:fpga|field programmable)\b": "FPGA",
    r"\b(?:vlsi|asic)\b": "VLSI/ASIC",
    r"\b(?:iot|internet of things)\b": "IoT",
    r"\b(?:ai|artificial intelligence|machine learning|deep learning)\b": "AI/ML",
    r"\b(?:blockchain|smart contract)\b": "blockchain",
    r"\b(?:drone|uav|quadcopter)\b": "drones/UAVs",
    r"\b(?:lidar|radar)\b": "LiDAR/radar",
    r"\b(?:gnss|gps)\b": "GNSS/GPS",
    r"\b(?:imu|inertial)\b": "IMU sensors",
    r"\b(?:mqtt|coap|http|grpc)\b": "communication protocols",
    r"\b(?:reinforcement learning|rl\b)\b": "reinforcement learning",
    r"\b(?:graph neural network|gnn)\b": "graph neural networks",
    r"\b(?:quantum)\b": "quantum computing",
    r"\b(?:xr|extended reality|vr|virtual reality|ar|augmented reality)\b": "XR/VR/AR",
    r"\b(?:edge computing|edge ai)\b": "edge computing",
    r"\b(?:digital twin)\b": "digital twin",
    r"\b(?:slam|localization|mapping)\b": "SLAM",
    r"\b(?:nlp|natural language)\b": "NLP",
    r"\b(?:computer vision|cv\b)\b": "computer vision",
    r"\b(?:sensor|actuator)\b": "sensors/actuators",
    r"\b(?:microcontroller|mcu)\b": "microcontrollers",
}


def extract_tech_from_title(title: str) -> str:
    """Extract technology keywords from title."""
    found = set()
    title_lower = title.lower()
    for pattern, tech in TITLE_TECH_PATTERNS.items():
        if re.search(pattern, title_lower):
            found.add(tech)
    return ", ".join(sorted(found)) if found else "machine learning"


def extract_action_from_title(title: str) -> str:
    """Extract action verb from title."""
    title_lower = title.lower()
    if any(w in title_lower for w in ["detect", "detection", "identify", "identification"]):
        return "detect and identify"
    if any(w in title_lower for w in ["monitor", "monitoring", "surveillance"]):
        return "monitor and analyze"
    if any(w in title_lower for w in ["predict", "prediction", "forecast"]):
        return "predict and forecast"
    if any(w in title_lower for w in ["control", "regulation", "manage"]):
        return "control and regulate"
    if any(w in title_lower for w in ["optimize", "optimization", "improve"]):
        return "optimize and improve"
    if any(w in title_lower for w in ["design", "develop", "create", "build", "implement"]):
        return "design and implement"
    if any(w in title_lower for w in ["analyze", "analysis", "classify", "classification"]):
        return "analyze and classify"
    if any(w in title_lower for w in ["secure", "security", "protect", "encrypt"]):
        return "secure and protect"
    if any(w in title_lower for w in ["navigate", "navigation", "localize", "mapping"]):
        return "navigate and map"
    if any(w in title_lower for w in ["communicate", "transmit", "transfer"]):
        return "communicate and transmit"
    return "process and analyze"


def extract_topic_from_title(title: str) -> str:
    """Extract main topic from title."""
    # Remove common prefixes
    title = re.sub(r"^(a|an|the|smart|ai-based|iot-based|deep learning|machine learning)\s+", "", title, flags=re.IGNORECASE)
    # Take first meaningful chunk
    words = title.split()[:8]
    return " ".join(words).strip(",. ")


def generate_abstract(row: dict) -> str:
    """Generate a synthetic abstract for a placeholder record."""
    domain = row.get("domain", "").strip()
    title = row.get("title", "").strip()
    tech_stack = row.get("tech_stack", "").strip()

    tech = tech_stack if tech_stack else extract_tech_from_title(title)
    action = extract_action_from_title(title)
    topic = extract_topic_from_title(title)

    template = DOMAIN_TEMPLATES.get(domain, GENERIC_TEMPLATE)

    try:
        abstract = template.format(
            topic=topic,
            action=action,
            tech=tech,
            data_type="environmental" if "environment" in domain.lower() else "operational",
            prediction_task="early warning" if "predict" in action else "anomaly detection",
            setting="public spaces" if "public" in domain.lower() else "operational environments",
            target="threats" if "security" in domain.lower() else "anomalies",
            accuracy="95",
            subject=topic,
            ml_method="deep learning" if "deep" in tech.lower() else "machine learning",
            traffic_type="network" if "network" in domain.lower() else "data",
            platform="FPGA" if "fpga" in tech.lower() else "ASIC",
            frequency="100",
            security_function="encryption" if "encrypt" in tech.lower() else "authentication",
            algorithm="AES" if "aes" in tech.lower() else "custom",
            security_property="confidentiality",
            document_type="technical documents" if "document" in topic.lower() else "text data",
            preprocessing="tokenization and normalization",
            model="BERT" if "transformer" in tech.lower() else "LSTM",
            task="classification" if "classif" in action else "extraction",
            dataset="benchmark datasets",
            hardware="ESP32-CAM" if "esp32" in tech.lower() else "embedded GPU",
            application=topic,
            model_type="MobileNet" if "mobile" in tech.lower() else "ResNet",
            fps="30",
            accuracy_pct="92",
            power="500",
            sensors="dissolved oxygen, pH, temperature sensors",
            parameters="water quality parameters",
            protocol="LoRaWAN",
            cloud_edge="cloud",
            analysis="trend analysis",
            conditions="critical thresholds",
            model_arch="CNN-LSTM",
            features="spatiotemporal features",
            detection="anomaly detection",
            dataset_name="custom dataset",
            metrics="high precision and recall",
            models="Random Forest, XGBoost, and Neural Networks",
            threat="intrusion",
            environment="production networks",
            performance="real-time",
            entities="users and items",
            task_desc="recommendation",
            gnn_type="GraphSAGE",
            layers="3",
            order="high",
            benchmarks="standard datasets",
            model_arch_pharma="YOLOv5",
            task_pharma="tablet counting and classification",
            image_type="conveyor belt imagery",
            speed="real-time",
            accuracy_pharma="99",
            consensus="Proof of Stake",
            language="Solidity",
            functionality="automated transactions",
            percentage="30",
            component="power converter",
            algorithm_opt="MPPT",
            topology="multi-level inverter",
            efficiency="97",
            conditions_energy="varying irradiance",
            mcu="ESP32",
            protocol_comm="MQTT",
            connectivity="cloud",
            battery_life="6 months",
            battery_type="Li-ion",
            structure="composite plates",
            simulation_tool="ANSYS",
            method="modal analysis",
            insight="vibration characteristics",
            phenomenon="cut-out effects",
            error="5",
            algorithm_eng="parallel processing",
            problem="large-scale optimization",
            architecture_eng="GPU cluster",
            speedup="10",
            baseline="CPU implementation",
            constraint="memory bandwidth",
            sensors_robot="LiDAR, IMU, camera",
            navigation_type="autonomous",
            trajectory="smooth and collision-free",
            planning_time="50ms",
            env_robot="unstructured terrain",
            function_vlsi="signal processing",
            process_node="28",
            frequency_vlsi="500",
            power_vlsi="50",
            signoff="Cadence",
            framework_cloud="Kubernetes",
            workload="microservices",
            consistency_model="eventual",
            guarantees="high availability",
            perf_cloud="low latency",
            nodes="1000",
            language_nlp="English",
            model_nlp="transformer",
            parameters_nlp="110M",
            score="state-of-the-art",
            benchmark_nlp="GLUE",
            domain_nlp="technical",
            architecture_cv="ResNet-50",
            task_cv="image classification",
            technique="attention mechanism",
            metric="top-1 accuracy",
            percentage_cv="3",
            data_cv="1M",
            augmentation="mixup and cutmix",
            method_eng="finite element analysis",
            problem_eng="structural optimization",
            implementation="C++/CUDA",
            performance_eng="real-time",
            hardware_eng="GPU cluster",
            testing_eng="benchmark validation",
            physiological="ECG",
            condition="arrhythmia",
            sensor_type="wearable ECG",
            resolution="1mV",
            comfort="high",
            accuracy_bio="98",
        )
    except KeyError:
        abstract = GENERIC_TEMPLATE.format(
            domain=domain,
            topic=topic,
            tech=tech,
            action=action,
            metric="performance",
            method="advanced algorithms",
            validation="extensive testing",
        )

    return f"[SYNTHETIC] {abstract}"


def main():
    with DATASET_PATH.open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    placeholder_count = 0
    for row in rows:
        if row["abstract"].strip() == "Description not independently verified.":
            row["abstract"] = generate_abstract(row)
            placeholder_count += 1

    # Write enriched dataset
    with OUTPUT_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=reader.fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Enriched {placeholder_count} placeholder abstracts")
    print(f"Output: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()