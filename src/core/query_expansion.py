"""Query expansion for improved recall."""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from typing import Any

logger = logging.getLogger(__name__)

# Common engineering synonyms and related terms
ENGINEERING_SYNONYMS = {
    "iot": ["internet of things", "connected devices", "smart sensors", "embedded systems"],
    "ai": ["artificial intelligence", "machine learning", "deep learning", "neural networks"],
    "ml": ["machine learning", "artificial intelligence", "predictive modeling"],
    "cnn": ["convolutional neural network", "deep learning", "computer vision"],
    "rnn": ["recurrent neural network", "sequence modeling", "lstm", "gru"],
    "transformer": ["attention mechanism", "bert", "gpt", "large language model"],
    "esp32": ["esp8266", "microcontroller", "embedded wifi", "iot hardware"],
    "raspberry pi": ["rpi", "single board computer", "embedded linux", "sbcs"],
    "arduino": ["microcontroller", "embedded", "avr", "atmega"],
    "fpga": ["field programmable gate array", "hardware acceleration", "verilog", "vhdl"],
    "pcb": ["printed circuit board", "circuit design", "hardware design"],
    "sensor": ["transducer", "detector", "measurement device"],
    "actuator": ["motor", "servo", "driver", "control output"],
    "monitoring": ["surveillance", "observation", "tracking", "supervision"],
    "detection": ["identification", "recognition", "classification", "sensing"],
    "classification": ["categorization", "pattern recognition", "labeling"],
    "prediction": ["forecasting", "estimation", "prognosis", "inference"],
    "optimization": ["improvement", "enhancement", "tuning", "maximization"],
    "control": ["regulation", "governance", "management", "automation"],
    "automation": ["automatic control", "robotics", "process control"],
    "robotics": ["autonomous systems", "manipulators", "mobile robots"],
    "drone": ["uav", "unmanned aerial vehicle", "quadcopter"],
    "autonomous": ["self-driving", "driverless", "independent navigation"],
    "navigation": ["localization", "path planning", "mapping", "slam"],
    "slam": ["simultaneous localization and mapping", "mapping", "localization"],
    "computer vision": ["image processing", "visual recognition", "cv"],
    "nlp": ["natural language processing", "text analysis", "language understanding"],
    "reinforcement learning": ["rl", "policy learning", "reward-based learning"],
    "supervised learning": ["labeled learning", "classification", "regression"],
    "unsupervised learning": ["clustering", "dimensionality reduction", "pattern discovery"],
    "anomaly detection": ["outlier detection", "anomaly identification", "novelty detection"],
    "predictive maintenance": ["condition monitoring", "failure prediction", "reliability"],
    "smart grid": ["intelligent grid", "power distribution", "energy management"],
    "renewable energy": ["solar", "wind", "hydro", "green energy", "sustainable power"],
    "battery": ["energy storage", "lithium-ion", "power cell"],
    "wireless": ["rf", "radio frequency", "bluetooth", "zigbee", "lora", "wifi"],
    "communication": ["telemetry", "data transmission", "networking"],
    "protocol": ["standard", "interface", "api", "communication protocol"],
    "security": ["cybersecurity", "protection", "authentication", "encryption"],
    "encryption": ["cryptography", "cipher", "secure communication"],
    "blockchain": ["distributed ledger", "smart contracts", "web3", "decentralized"],
    "cloud": ["aws", "azure", "gcp", "cloud computing", "distributed systems"],
    "edge computing": ["edge ai", "fog computing", "local processing"],
    "microservices": ["service oriented architecture", "distributed services"],
    "container": ["docker", "kubernetes", "orchestration"],
    "database": ["sql", "nosql", "data storage", "persistence"],
    "api": ["rest", "graphql", "grpc", "interface", "endpoint"],
    "dashboard": ["visualization", "monitoring ui", "control panel"],
    "real-time": ["live", "streaming", "low latency", "synchronous"],
    "low power": ["energy efficient", "ultra low power", "battery operated"],
    "wearable": ["wearable tech", "body sensor", "health monitoring"],
    "biomedical": ["medical device", "healthcare", "clinical", "physiological"],
    "agriculture": ["farming", "precision agriculture", "crop monitoring"],
    "aquaculture": ["fish farming", "aquatic farming", "water quality"],
    "manufacturing": ["industrial", "production", "factory automation"],
    "supply chain": ["logistics", "inventory", "tracking"],
    "transportation": ["vehicle", "traffic", "mobility", "automotive"],
    "smart city": ["urban computing", "city infrastructure", "municipal"],
    "environmental": ["sustainability", "climate", "pollution monitoring"],
    "water quality": ["water monitoring", "water treatment", "hydroinformatics"],
    "air quality": ["air monitoring", "pollution detection", "emissions"],
    "structural health": ["shm", "infrastructure monitoring", "civil engineering"],
    "vibration": ["oscillation", "mechanical vibration", "modal analysis"],
    "thermal": ["temperature", "heat", "thermodynamics", "cooling"],
    "acoustic": ["sound", "audio", "noise", "ultrasonic"],
    "optical": ["light", "photonics", "laser", "fiber optic"],
    "magnetic": ["magnetism", "electromagnetic", "inductive"],
    "pressure": ["force", "stress", "strain", "load cell"],
    "flow": ["fluid dynamics", "flow rate", "hydraulics", "pneumatics"],
    "humidity": ["moisture", "dew point", "relative humidity"],
    "ph": ["acidity", "alkalinity", "chemical balance"],
    "conductivity": ["electrical conductivity", "salinity", "tds"],
    "dissolved oxygen": ["do", "oxygen level", "aeration"],
    "turbidity": ["water clarity", "suspended solids", "ntu"],
    "gps": ["gnss", "positioning", "satellite navigation", "location"],
    "imu": ["inertial measurement", "accelerometer", "gyroscope", "magnetometer"],
    "lidar": ["laser scanning", "3d mapping", "time of flight"],
    "radar": ["radio detection", "ranging", "mmwave"],
    "camera": ["imaging", "vision sensor", "ccd", "cmos"],
    "microphone": ["audio sensor", "sound detection", "acoustic sensor"],
    "speaker": ["audio output", "actuator", "sound generation"],
    "display": ["screen", "led", "oled", "lcd", "e-ink"],
    "touchscreen": ["touch panel", "capacitive touch", "resistive touch"],
    "button": ["switch", "input", "user interface"],
    "led": ["light emitting diode", "indicator", "illumination"],
    "motor": ["actuator", "drive", "stepper", "servo", "dc motor", "bldc"],
    "pump": ["fluid pump", "peristaltic", "diaphragm", "centrifugal"],
    "valve": ["solenoid", "control valve", "flow control"],
    "relay": ["switch", "contactor", "solid state relay"],
    "fuse": ["circuit breaker", "protection", "overcurrent"],
    "regulator": ["voltage regulator", "ldo", "buck", "boost", "buck-boost"],
    "converter": ["dc-dc", "ac-dc", "inverter", "power supply"],
    "transformer": ["power transformer", "isolation", "step-up", "step-down"],
    "capacitor": ["cap", "energy storage", "filtering", "decoupling"],
    "inductor": ["coil", "choke", "magnetic component"],
    "resistor": ["resistance", "current limiting", "voltage divider"],
    "diode": ["rectifier", "protection", "led", "zener", "schottky"],
    "transistor": ["mosfet", "bjt", "igbt", "switching", "amplification"],
    "ic": ["integrated circuit", "chip", "microchip", "asic", "fpga"],
    "mcu": ["microcontroller", "microprocessor", "embedded processor"],
    "cpu": ["processor", "central processing unit", "core"],
    "gpu": ["graphics processor", "parallel computing", "accelerator"],
    "ram": ["memory", "random access memory", "dram", "sram"],
    "rom": ["flash", "eeprom", "non-volatile memory", "storage"],
    "adc": ["analog to digital", "analog input", "data acquisition"],
    "dac": ["digital to analog", "analog output"],
    "pwm": ["pulse width modulation", "motor control", "dimming"],
    "i2c": ["iic", "two wire interface", "serial bus"],
    "spi": ["serial peripheral interface", "synchronous serial"],
    "uart": ["serial", "rs232", "async serial", "com port"],
    "usb": ["universal serial bus", "usb-c", "usb-pd"],
    "ethernet": ["lan", "wired network", "tcp/ip"],
    "wifi": ["802.11", "wireless lan", "wlan"],
    "bluetooth": ["ble", "bluetooth low energy", "wireless personal area"],
    "zigbee": ["802.15.4", "mesh network", "low power wireless"],
    "lora": ["long range", "lorawan", "low power wide area"],
    "nb-iot": ["narrowband iot", "cellular iot", "lpwan"],
    "5g": ["fifth generation", "mobile network", "cellular"],
    "mqtt": ["message queuing", "pub/sub", "iot protocol"],
    "coap": ["constrained application", "iot protocol", "udp"],
    "http": ["rest api", "web api", "hypertext transfer"],
    "websocket": ["real-time", "full duplex", "persistent connection"],
    "grpc": ["remote procedure call", "protobuf", "high performance"],
}


def expand_query(query: str, max_expansions: int = 10) -> list[str]:
    """Expand query with engineering synonyms.

    Args:
        query: Original query string
        max_expansions: Maximum number of expansion terms to add

    Returns:
        List of expanded terms (original query terms + synonyms)
    """
    if not query:
        return []

    # Tokenize query
    tokens = re.findall(r"[a-z0-9+#.-]+", query.lower())
    if not tokens:
        return []

    # Find expansions
    expansions: set[str] = set(tokens)
    for token in tokens:
        if token in ENGINEERING_SYNONYMS:
            for syn in ENGINEERING_SYNONYMS[token]:
                if len(expansions) >= max_expansions + len(tokens):
                    break
                expansions.add(syn)

    return list(expansions)


def build_expanded_query(query: str, max_terms: int = 20) -> str:
    """Build an expanded query string for search APIs.

    Args:
        query: Original query
        max_terms: Maximum total terms in expanded query

    Returns:
        Expanded query string
    """
    expanded = expand_query(query)
    # Prioritize original terms, then add expansions
    original = re.findall(r"[a-z0-9+#.-]+", query.lower())
    # Keep original order for original terms, append expansions
    result = []
    seen = set()
    for term in original:
        if term not in seen:
            result.append(term)
            seen.add(term)
    for term in expanded:
        if term not in seen and len(result) < max_terms:
            result.append(term)
            seen.add(term)
    return " ".join(result)


@lru_cache(maxsize=128)
def get_cached_expansion(query: str) -> list[str]:
    """Cached query expansion for repeated queries."""
    return expand_query(query)