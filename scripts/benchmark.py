#!/usr/bin/env python3
"""Benchmark evaluation framework for search quality measurement."""

from __future__ import annotations

import asyncio
import csv
import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from src.core.contracts import ProjectRecord
from src.core.dataset_loader import load_project_records
from src.core.engine import CoreSearchEngine
from src.core.bm25_retriever import BM25Retriever
from src.core.vector_retriever import VectorRetriever
from src.live_search.service import LiveSearchService
from src.live_search.contracts import SearchState


BENCHMARK_DIR = Path("data/benchmark")
BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)

QUERIES_FILE = BENCHMARK_DIR / "queries.json"
LABELS_FILE = BENCHMARK_DIR / "labels.csv"
RESULTS_DIR = BENCHMARK_DIR / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class BenchmarkQuery:
    id: str
    text: str
    category: str
    expected_domains: list[str] = field(default_factory=list)


@dataclass
class RelevanceLabel:
    query_id: str
    candidate_id: str
    candidate_type: str  # "local" | "paper" | "repository"
    grade: int  # 0-3
    rationale: str = ""
    confidence: str = "medium"  # low|medium|high


DEFAULT_QUERIES = [
    BenchmarkQuery("q1", "IoT-based crop disease detection using Raspberry Pi and CNN for real-time foliar infection monitoring", "Agriculture/IoT", ["IoT", "Computer Vision", "Agriculture"]),
    BenchmarkQuery("q2", "Smart door lock system with facial recognition using ESP32-CAM for biometric access control", "IoT/Security", ["IoT", "Embedded Vision", "Security"]),
    BenchmarkQuery("q3", "Deep learning anomaly detection in surveillance video using CNN and RNN for violence detection", "Computer Vision", ["Computer Vision", "Video Analytics", "Deep Learning"]),
    BenchmarkQuery("q4", "Network intrusion detection for IoT botnet attacks using machine learning ensemble classifiers", "Cybersecurity", ["Cybersecurity", "Network Defense", "Machine Learning"]),
    BenchmarkQuery("q5", "Quantum teleportation device for household pets using acoustic levitation", "Quantum/Novelty", ["Quantum", "Physics"]),
    BenchmarkQuery("q6", "Autonomous lunar rover navigation using reinforcement learning and orbital DEMs", "Robotics/Space", ["Robotics", "Autonomous Systems", "Reinforcement Learning"]),
    BenchmarkQuery("q7", "AI-assisted swarm robotics with ant colony optimization for dynamic exploration", "Robotics/AI", ["Robotics", "Swarm Intelligence", "AI"]),
    BenchmarkQuery("q8", "Edge-optimized Indian Sign Language translator using landmark-based motion representation", "Assistive Tech/Edge AI", ["Computer Vision", "Edge Computing", "Assistive Technology"]),
    BenchmarkQuery("q9", "Hydrogen fuel-cell utility aircraft conceptual design with PEM fuel cells for sustainable aviation", "Aerospace/Energy", ["Aerospace", "Power Systems", "Renewable Energy"]),
    BenchmarkQuery("q10", "FPGA-based AES encryption system for hardware security and data protection", "Hardware Security", ["Hardware Security", "VLSI", "FPGA"]),
    BenchmarkQuery("q11", "Smart aquaculture monitoring system with ESP32 for dissolved oxygen, pH, temperature", "IoT/Agriculture", ["IoT", "Smart Agriculture", "Embedded Systems"]),
    BenchmarkQuery("q12", "Graph neural network recommendation system for social platforms modeling high-order user interactions", "Graph ML", ["Data Science", "Graph Machine Learning", "Recommendation Systems"]),
    BenchmarkQuery("q13", "Deep learning capsule and tablet identification for pharmaceutical inspection using YOLO", "Healthcare/Vision", ["Healthcare AI", "Pharmaceutical Vision", "Object Detection"]),
    BenchmarkQuery("q14", "Virtual reality aerospace maintenance hangar walkthrough for training simulation", "VR/Training", ["Virtual Reality", "Aerospace", "Simulation"]),
    BenchmarkQuery("q15", "Blockchain-based decentralized document storage with NFT authentication", "Blockchain", ["Blockchain", "Decentralized Systems", "Security"]),
]


def ensure_queries_file() -> None:
    if not QUERIES_FILE.exists():
        data = [asdict(q) for q in DEFAULT_QUERIES]
        QUERIES_FILE.write_text(json.dumps(data, indent=2))
        print(f"Created {QUERIES_FILE} with {len(data)} default queries")
    else:
        print(f"Queries file exists: {QUERIES_FILE}")


def ensure_labels_file() -> None:
    if not LABELS_FILE.exists():
        with LABELS_FILE.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["query_id", "candidate_id", "candidate_type", "grade", "rationale", "confidence"])
        print(f"Created {LABELS_FILE}")
    else:
        print(f"Labels file exists: {LABELS_FILE}")


def load_labels() -> list[RelevanceLabel]:
    labels = []
    if LABELS_FILE.exists():
        with LABELS_FILE.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                labels.append(RelevanceLabel(
                    query_id=row["query_id"],
                    candidate_id=row["candidate_id"],
                    candidate_type=row["candidate_type"],
                    grade=int(row["grade"]),
                    rationale=row.get("rationale", ""),
                    confidence=row.get("confidence", "medium")
                ))
    return labels


async def run_local_search(query: str, top_k: int = 20) -> list[dict[str, Any]]:
    records = load_project_records()
    engine = CoreSearchEngine(records, BM25Retriever(records), VectorRetriever(records, auto_build=False))
    matches = engine.search(query, top_k)
    return [
        {
            "candidate_id": f"local:{m.project.project_id}",
            "candidate_type": "local",
            "title": m.project.title,
            "description": m.project.abstract,
            "source_url": m.project.source_url,
            "source_type": m.project.source_type,
            "year": m.project.year,
            "domain": m.project.domain,
            "tech_stack": m.project.tech_stack,
            "rank": m.rank,
            "bm25_rank": m.bm25_rank,
            "vector_rank": m.vector_rank,
            "rrf_score": m.rrf_score,
            "shared_elements": m.shared_elements,
            "verification_status": m.verification_status,
        }
        for m in matches
    ]


async def run_live_search(query: str, top_k: int = 20) -> list[dict[str, Any]]:
    service = LiveSearchService()
    await service.start()
    try:
        outcome = await service.search(query, top_k)
        return [
            {
                "candidate_id": m["candidate_id"],
                "candidate_type": m.get("candidate_type", "unknown"),
                "title": m["title"],
                "description": m.get("description", ""),
                "source_url": m.get("source_url"),
                "source_type": "research_paper" if m.get("candidate_type") == "paper" else "open_source_repository",
                "source_provider": m.get("source_provider"),
                "rank": m["rank"],
                "bm25_rank": m.get("bm25_rank"),
                "dense_rank": m.get("dense_rank"),
                "rrf_score": m["rrf_score"],
                "shared_concepts": m.get("shared_concepts", []),
                "distinctive_terms": m.get("distinctive_terms", []),
                "explanation": m.get("explanation", ""),
            }
            for m in outcome.matches
        ]
    finally:
        await service.close()


async def capture_candidate_pool() -> None:
    """Capture full candidate pools for all benchmark queries."""
    queries_data = json.loads(QUERIES_FILE.read_text())
    queries = [BenchmarkQuery(**q) for q in queries_data]

    print(f"Capturing candidate pools for {len(queries)} queries...")

    for query in queries:
        print(f"\n  Query {query.id}: {query.text[:60]}...")

        # Local search (max 20 per engine limits)
        local_results = await run_local_search(query.text, top_k=20)
        print(f"    Local: {len(local_results)} candidates")

        # Live search (max 20 per API limits)
        try:
            live_results = await run_live_search(query.text, top_k=20)
            print(f"    Live: {len(live_results)} candidates")
        except Exception as e:
            print(f"    Live: ERROR - {e}")
            live_results = []

        # Save
        pool = {
            "query_id": query.id,
            "query_text": query.text,
            "category": query.category,
            "timestamp": time.time(),
            "local_candidates": local_results,
            "live_candidates": live_results,
        }

        out_file = RESULTS_DIR / f"pool_{query.id}.json"
        out_file.write_text(json.dumps(pool, indent=2))

    print(f"\nAll pools saved to {RESULTS_DIR}/")


def export_annotation_sheet() -> None:
    """Export a CSV for human labeling of all captured candidates."""
    pools = list(RESULTS_DIR.glob("pool_*.json"))
    if not pools:
        print("No candidate pools found. Run capture_candidate_pool() first.")
        return

    all_rows = []
    fieldnames = [
        "query_id", "candidate_id", "candidate_type", "title", "description",
        "source_url", "source_type", "source_provider", "year", "domain",
        "shared_elements", "shared_concepts", "grade", "rationale", "confidence"
    ]

    for pool_file in pools:
        pool = json.loads(pool_file.read_text())
        query_id = pool["query_id"]

        for cand in pool["local_candidates"]:
            all_rows.append({
                "query_id": query_id,
                "candidate_id": cand["candidate_id"],
                "candidate_type": "local",
                "title": cand["title"],
                "description": (cand.get("description") or "")[:500],
                "source_url": cand.get("source_url", ""),
                "source_type": cand.get("source_type", ""),
                "source_provider": "",
                "year": cand.get("year", ""),
                "domain": cand.get("domain", ""),
                "shared_elements": ", ".join(cand.get("shared_elements", [])),
                "shared_concepts": "",
                "grade": "",
                "rationale": "",
                "confidence": "",
            })

        for cand in pool["live_candidates"]:
            all_rows.append({
                "query_id": query_id,
                "candidate_id": cand["candidate_id"],
                "candidate_type": cand.get("source_type", "unknown"),
                "title": cand["title"],
                "description": (cand.get("description") or "")[:500],
                "source_url": cand.get("source_url", ""),
                "source_type": cand.get("source_type", ""),
                "source_provider": cand.get("source_provider", ""),
                "year": "",
                "domain": "",
                "shared_elements": "",
                "shared_concepts": ", ".join(cand.get("shared_concepts", [])),
                "grade": "",
                "rationale": "",
                "confidence": "",
            })

    out_file = BENCHMARK_DIR / "annotation_sheet.csv"
    with out_file.open("w", encoding="utf-8", newline="") as f:
        if all_rows:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_rows)

    print(f"Annotation sheet exported: {out_file} ({len(all_rows)} candidates)")


def load_reviewed_labels() -> list[RelevanceLabel]:
    """Load human-reviewed labels from annotation sheet."""
    labels = []
    annotation_file = BENCHMARK_DIR / "annotation_sheet_reviewed.csv"
    if not annotation_file.exists():
        annotation_file = LABELS_FILE
    if annotation_file.exists():
        with annotation_file.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("grade") and row["grade"].strip():
                    labels.append(RelevanceLabel(
                        query_id=row["query_id"],
                        candidate_id=row["candidate_id"],
                        candidate_type=row["candidate_type"],
                        grade=int(row["grade"]),
                        rationale=row.get("rationale", ""),
                        confidence=row.get("confidence", "medium")
                    ))
    return labels


def evaluate_rankings() -> dict[str, Any]:
    """Evaluate BM25, dense, and hybrid rankings against human labels."""
    labels = load_reviewed_labels()
    if not labels:
        print("No reviewed labels found. Complete annotation_sheet_reviewed.csv first.")
        return {}

    # Group by query
    by_query: dict[str, list[RelevanceLabel]] = {}
    for label in labels:
        by_query.setdefault(label.query_id, []).append(label)

    # Load candidate pools
    pools = {}
    for pool_file in RESULTS_DIR.glob("pool_*.json"):
        pool = json.loads(pool_file.read_text())
        pools[pool["query_id"]] = pool

    results = {
        "queries_evaluated": len(by_query),
        "total_labels": len(labels),
        "grade_distribution": Counter(l.grade for l in labels),
        "per_query": {},
        "aggregate": {}
    }

    for query_id, q_labels in by_query.items():
        pool = pools.get(query_id)
        if not pool:
            continue

        # Build candidate lookup
        local_by_id = {c["candidate_id"]: c for c in pool["local_candidates"]}
        live_by_id = {c["candidate_id"]: c for c in pool["live_candidates"]}

        # Get ranked orders
        local_ranked = sorted(pool["local_candidates"], key=lambda c: c["rank"])
        live_ranked = sorted(pool["live_candidates"], key=lambda c: c["rank"])

        # Evaluate each ranking method
        label_by_id = {l.candidate_id: l for l in q_labels}
        relevant_ids = {l.candidate_id for l in q_labels if l.grade > 0}

        def eval_ranking(ranked_list, name):
            if not ranked_list:
                return {"precision_at_5": 0, "recall_at_10": 0, "ndcg_at_10": 0, "mrr_at_10": 0}

            # Precision@5
            top5 = ranked_list[:5]
            prec5 = sum(1 for c in top5 if label_by_id.get(c["candidate_id"], RelevanceLabel("", c["candidate_id"], "", 0)).grade > 0) / 5

            # Recall@10
            top10 = ranked_list[:10]
            found_relevant = sum(1 for c in top10 if label_by_id.get(c["candidate_id"], RelevanceLabel("", c["candidate_id"], "", 0)).grade > 0)
            rec10 = found_relevant / len(relevant_ids) if relevant_ids else 0

            # nDCG@10
            dcg = 0
            for i, c in enumerate(top10):
                grade = label_by_id.get(c["candidate_id"], RelevanceLabel("", c["candidate_id"], "", 0)).grade
                if grade > 0:
                    dcg += grade / (i + 1).__import__("math").log2(i + 2) if i > 0 else grade

            # Ideal DCG
            ideal_grades = sorted([l.grade for l in q_labels if l.grade > 0], reverse=True)
            idcg = sum(g / ((i + 1).__import__("math").log2(i + 2) if i > 0 else 1) for i, g in enumerate(ideal_grades[:10]))
            ndcg = dcg / idcg if idcg > 0 else 0

            # MRR@10
            mrr = 0
            for i, c in enumerate(top10):
                if label_by_id.get(c["candidate_id"], RelevanceLabel("", c["candidate_id"], "", 0)).grade > 0:
                    mrr = 1 / (i + 1)
                    break

            return {"precision_at_5": prec5, "recall_at_10": rec10, "ndcg_at_10": ndcg, "mrr_at_10": mrr}

        results["per_query"][query_id] = {
            "local": eval_ranking(local_ranked, "local"),
            "live": eval_ranking(live_ranked, "live"),
        }

    # Aggregate
    for method in ["local", "live"]:
        metrics = {m: [] for m in ["precision_at_5", "recall_at_10", "ndcg_at_10", "mrr_at_10"]}
        for q in results["per_query"].values():
            for m in metrics:
                metrics[m].append(q[method][m])
        results["aggregate"][method] = {m: sum(v)/len(v) if v else 0 for m, v in metrics.items()}

    return results


async def main():
    import sys
    if len(sys.argv) < 2:
        print("Usage: python benchmark.py [init|capture|export|eval]")
        return

    cmd = sys.argv[1]

    if cmd == "init":
        ensure_queries_file()
        ensure_labels_file()
    elif cmd == "capture":
        await capture_candidate_pool()
    elif cmd == "export":
        export_annotation_sheet()
    elif cmd == "eval":
        results = evaluate_rankings()
        print(json.dumps(results, indent=2))
    else:
        print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    asyncio.run(main())