"""Hybrid search orchestration with smart routing."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, List, Optional

from src.core.contracts import ProjectRecord
from src.core.engine import CoreSearchEngine
from src.live_search.service import LiveSearchService, LiveSearchUnavailable
from src.live_search.contracts import SearchState

logger = logging.getLogger(__name__)


@dataclass
class HybridSearchConfig:
    """Configuration for hybrid search behavior."""
    innovation_threshold: float = 0.7
    common_query_cache_ttl: int = 3600
    enable_cross_encoder: bool = True
    enable_citation_expansion: bool = True
    enable_query_expansion: bool = True
    local_first_domains: List[str] = None
    live_first_domains: List[str] = None

    def __post_init__(self):
        if self.local_first_domains is None:
            self.local_first_domains = [
                "iot", "embedded", "microcontroller", "arduino", "esp32", "raspberry pi",
                "sensor", "actuator", "pcb", "circuit", "power electronics",
                "control systems", "automation", "robotics", "mechatronics"
            ]
        if self.live_first_domains is None:
            self.live_first_domains = [
                "quantum", "blockchain", "llm", "transformer", "generative ai",
                "foundation model", "diffusion", "neural radiance", "nerf",
                "quantum computing", "neuromorphic", "photonic computing"
            ]


@dataclass
class QueryAnalysis:
    """Analysis of a search query for routing decisions."""
    query: str
    complexity_score: float
    novelty_score: float
    domain_indicators: List[str]
    technical_terms: List[str]
    is_common_domain: bool
    is_novel_domain: bool
    recommended_mode: str  # "local", "live", "hybrid"
    confidence: float


class QueryAnalyzer:
    """Analyzes queries to determine optimal search strategy."""

    COMMON_PATTERNS = [
        r"\b(iot|internet of things)\b",
        r"\b(embedded|microcontroller|mcu)\b",
        r"\b(arduino|esp32|esp8266|raspberry pi|rpi)\b",
        r"\b(sensor|actuator|pcb|circuit)\b",
        r"\b(control|automation|pid|plc)\b",
        r"\b(robot|robotics|mechatronics)\b",
        r"\b(power electronics|converter|inverter)\b",
        r"\b(communication|wifi|bluetooth|zigbee|lora|mqtt)\b",
    ]

    NOVEL_PATTERNS = [
        r"\b(quantum|qubit|superposition|entanglement)\b",
        r"\b(blockchain|smart contract|web3|defi)\b",
        r"\b(llm|large language model|transformer|bert|gpt)\b",
        r"\b(generative ai|diffusion|stable diffusion|midjourney)\b",
        r"\b(foundation model|multimodal|vision language)\b",
        r"\b(neural radiance|nerf|3d gaussian)\b",
        r"\b(quantum computing|quantum algorithm)\b",
        r"\b(neuromorphic|spiking neural|photonic computing)\b",
        r"\b(protein folding|alphafold|drug discovery)\b",
    ]

    def __init__(self, config: HybridSearchConfig):
        self.config = config
        import re
        self.common_regex = [re.compile(p, re.IGNORECASE) for p in self.COMMON_PATTERNS]
        self.novel_regex = [re.compile(p, re.IGNORECASE) for p in self.NOVEL_PATTERNS]

    def analyze(self, query: str) -> QueryAnalysis:
        """Analyze query and return routing recommendation."""
        query_lower = query.lower()
        
        # Extract technical terms
        import re
        technical_terms = re.findall(r'\b[a-z]{3,}\b', query_lower)
        technical_terms = [t for t in technical_terms if len(t) > 3][:20]
        
        # Check common patterns
        common_matches = sum(1 for regex in self.common_regex if regex.search(query_lower))
        novel_matches = sum(1 for regex in self.novel_regex if regex.search(query_lower))
        
        # Domain indicators
        domain_indicators = []
        for domain in self.config.local_first_domains:
            if domain.lower() in query_lower:
                domain_indicators.append(domain)
        for domain in self.config.live_first_domains:
            if domain.lower() in query_lower:
                domain_indicators.append(domain)
        
        # Calculate scores
        complexity_score = min(1.0, len(query) / 500 + len(technical_terms) / 50)
        novelty_score = min(1.0, novel_matches * 0.3 + (1 - common_matches * 0.15))
        
        is_common_domain = common_matches > novel_matches
        is_novel_domain = novel_matches > common_matches
        
        # Determine recommended mode
        if is_novel_domain and novelty_score > self.config.innovation_threshold:
            recommended_mode = "live"
            confidence = min(0.9, novelty_score)
        elif is_common_domain and common_matches >= 2:
            recommended_mode = "local"
            confidence = min(0.9, 0.5 + common_matches * 0.1)
        else:
            recommended_mode = "hybrid"
            confidence = 0.7
        
        return QueryAnalysis(
            query=query,
            complexity_score=complexity_score,
            novelty_score=novelty_score,
            domain_indicators=domain_indicators,
            technical_terms=technical_terms,
            is_common_domain=is_common_domain,
            is_novel_domain=is_novel_domain,
            recommended_mode=recommended_mode,
            confidence=confidence
        )


class HybridSearchService:
    """Orchestrates local and live search with smart routing."""

    def __init__(
        self,
        core_engine: CoreSearchEngine,
        live_service: LiveSearchService,
        config: Optional[HybridSearchConfig] = None
    ):
        self.core_engine = core_engine
        self.live_service = live_service
        self.config = config or HybridSearchConfig()
        self.analyzer = QueryAnalyzer(self.config)
        self._cache = {}
        self._cache_timestamps = {}

    def _get_cache_key(self, query: str, mode: str, top_k: int) -> str:
        import hashlib
        return hashlib.sha256(f"{query}:{mode}:{top_k}".encode()).hexdigest()[:16]

    def _is_cache_valid(self, key: str) -> bool:
        if key not in self._cache_timestamps:
            return False
        age = time.time() - self._cache_timestamps[key]
        return age < self.config.common_query_cache_ttl

    async def search(
        self,
        query: str,
        top_k: int = 5,
        mode: str = "auto"
    ) -> dict[str, Any]:
        """
        Execute hybrid search with smart routing.
        
        Returns dict with matches, mode_used, analysis, and metadata.
        """
        start_time = time.time()
        
        # Analyze query
        analysis = self.analyzer.analyze(query)
        
        # Determine actual mode
        if mode == "auto":
            actual_mode = analysis.recommended_mode
        else:
            actual_mode = mode
        
        # Check cache for local/hybrid modes
        cache_key = self._get_cache_key(query, actual_mode, top_k)
        if actual_mode in ("local", "hybrid") and self._is_cache_valid(cache_key):
            cached = self._cache[cache_key]
            cached["from_cache"] = True
            cached["analysis"] = analysis.__dict__
            cached["mode_used"] = actual_mode
            return cached
        
        # Execute search based on mode
        local_results = []
        live_results = []
        warnings = []
        mode_used = actual_mode
        
        if actual_mode in ("local", "hybrid"):
            try:
                local_matches = self.core_engine.search(query, top_k)
                local_results = [self._match_to_dict(m) for m in local_matches]
            except Exception as e:
                logger.warning("Local search failed: %s", e)
                warnings.append(f"Local search unavailable: {e}")
                if actual_mode == "local":
                    mode_used = "failed"
        
        if actual_mode in ("live", "hybrid"):
            try:
                await self.live_service.start()
                live_outcome = await self.live_service.search(query, top_k)
                live_results = list(live_outcome.matches)
                if live_outcome.state != "complete":
                    warnings.append(f"Live search: {live_outcome.state}")
            except LiveSearchUnavailable as e:
                logger.warning("Live search unavailable: %s", e)
                warnings.append(f"Live providers unavailable: {e.providers}")
                if actual_mode == "live":
                    mode_used = "failed"
            except Exception as e:
                logger.warning("Live search failed: %s", e)
                warnings.append(f"Live search error: {e}")
                if actual_mode == "live":
                    mode_used = "failed"
            finally:
                await self.live_service.close()
        
        # Combine results
        if actual_mode == "hybrid":
            combined = self._fuse_results(local_results, live_results, top_k)
        elif actual_mode == "local":
            combined = local_results
        elif actual_mode == "live":
            combined = live_results
        else:
            combined = []
        
        # Apply cross-encoder reranking if enabled
        if self.config.enable_cross_encoder and combined:
            combined = await self._rerank_with_cross_encoder(query, combined, top_k)
        
        result = {
            "matches": combined[:top_k],
            "mode_used": mode_used,
            "analysis": analysis.__dict__,
            "warnings": warnings,
            "latency_ms": int((time.time() - start_time) * 1000),
            "result_count": len(combined),
            "local_count": len(local_results),
            "live_count": len(live_results)
        }
        
        # Cache for local/hybrid modes
        if actual_mode in ("local", "hybrid") and mode_used != "failed":
            self._cache[cache_key] = result
            self._cache_timestamps[cache_key] = time.time()
        
        return result

    def _match_to_dict(self, match) -> dict:
        """Convert SearchMatch to dict."""
        m = match.project
        return {
            "candidate_id": f"local:{m.project_id}",
            "source_type": m.source_type,
            "title": m.title,
            "description": m.abstract,
            "source_url": m.source_url,
            "source_provider": "local",
            "year": m.year,
            "domain": m.domain,
            "tech_stack": m.tech_stack,
            "rank": match.rank,
            "bm25_rank": match.bm25_rank,
            "vector_rank": match.vector_rank,
            "rrf_score": match.rrf_score,
            "shared_elements": list(match.shared_elements),
            "verification_status": match.verification_status
        }

    def _fuse_results(self, local: List[dict], live: List[dict], top_k: int) -> List[dict]:
        """Fuse local and live results using RRF."""
        # Simple RRF fusion
        all_results = {}
        
        for i, r in enumerate(local):
            key = r["candidate_id"]
            all_results[key] = r
            all_results[key]["local_rank"] = i + 1
        
        for i, r in enumerate(live):
            key = r["candidate_id"]
            if key in all_results:
                all_results[key]["live_rank"] = i + 1
            else:
                all_results[key] = r
                all_results[key]["live_rank"] = i + 1
        
        # Calculate RRF scores
        k = 60
        for r in all_results.values():
            local_rank = r.get("local_rank", 1000)
            live_rank = r.get("live_rank", 1000)
            r["rrf_score"] = 1/(k + local_rank) + 1/(k + live_rank)
            r["rank"] = 0  # Will be set after sorting
        
        # Sort by RRF score
        fused = sorted(all_results.values(), key=lambda x: x["rrf_score"], reverse=True)
        for i, r in enumerate(fused):
            r["rank"] = i + 1
        
        return fused

    async def _rerank_with_cross_encoder(self, query: str, results: List[dict], top_k: int) -> List[dict]:
        """Rerank results using cross-encoder."""
        try:
            from src.core.reranker import rerank_live_with_cross_encoder
            return rerank_live_with_cross_encoder(query, results, top_k)
        except Exception as e:
            logger.warning("Cross-encoder reranking failed: %s", e)
            return results

    def clear_cache(self):
        """Clear the search cache."""
        self._cache.clear()
        self._cache_timestamps.clear()


async def create_hybrid_search_service() -> HybridSearchService:
    """Factory to create hybrid search service with default config."""
    from src.database import _get_engine
    from src.live_search.service import LiveSearchService
    
    config = HybridSearchConfig(
        innovation_threshold=float(os.getenv("HYBRID_INNOVATION_THRESHOLD", "0.7")),
        common_query_cache_ttl=int(os.getenv("HYBRID_CACHE_TTL", "3600")),
        enable_cross_encoder=os.getenv("USE_CROSS_ENCODER", "1").lower() not in {"0", "false", "no"},
        enable_citation_expansion=os.getenv("LIVE_CITATION_EXPANSION", "0").lower() not in {"0", "false", "no"},
        enable_query_expansion=os.getenv("LIVE_QUERY_EXPANSION", "0").lower() not in {"0", "false", "no"}
    )
    
    core_engine = _get_engine()
    live_service = LiveSearchService()
    await live_service.start()
    
    return HybridSearchService(core_engine, live_service, config)