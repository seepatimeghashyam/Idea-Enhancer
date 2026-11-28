"""Multi-model AI enhancement with provider abstraction."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

from src.enhance.contracts import EnhanceResponse as EnhancementOutput

logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    """Configuration for a model provider."""
    id: str
    name: str
    provider: str  # gemini, openrouter, huggingface, groq, ollama
    api_base: str
    requires_key: bool = True
    free_tier: str = ""
    max_tokens: int = 4096
    supports_streaming: bool = False
    cost_per_1k: float = 0.0


# Model registry
MODEL_REGISTRY: Dict[str, ModelConfig] = {
    # Gemini
    "gemini-1.5-flash": ModelConfig(
        id="gemini-1.5-flash",
        name="Gemini 1.5 Flash",
        provider="gemini",
        api_base="https://generativelanguage.googleapis.com/v1beta",
        free_tier="1500 req/day",
        max_tokens=8192
    ),
    "gemini-1.5-pro": ModelConfig(
        id="gemini-1.5-pro",
        name="Gemini 1.5 Pro",
        provider="gemini",
        api_base="https://generativelanguage.googleapis.com/v1beta",
        max_tokens=8192
    ),
    "gemini-1.5-flash-lite": ModelConfig(
        id="gemini-1.5-flash-lite",
        name="Gemini 1.5 Flash-Lite",
        provider="gemini",
        api_base="https://generativelanguage.googleapis.com/v1beta",
        free_tier="1500 req/day",
        max_tokens=8192
    ),
    # OpenRouter
    "openrouter:mistralai/mixtral-8x7b-instruct": ModelConfig(
        id="openrouter:mistralai/mixtral-8x7b-instruct",
        name="Mixtral 8x7B Instruct",
        provider="openrouter",
        api_base="https://openrouter.ai/api/v1",
        free_tier="50 req/day",
        max_tokens=32768
    ),
    "openrouter:meta-llama/llama-3-70b-instruct": ModelConfig(
        id="openrouter:meta-llama/llama-3-70b-instruct",
        name="Llama 3 70B Instruct",
        provider="openrouter",
        api_base="https://openrouter.ai/api/v1",
        free_tier="50 req/day",
        max_tokens=8192
    ),
    "openrouter:qwen/qwen-2.5-72b-instruct": ModelConfig(
        id="openrouter:qwen/qwen-2.5-72b-instruct",
        name="Qwen 2.5 72B Instruct",
        provider="openrouter",
        api_base="https://openrouter.ai/api/v1",
        free_tier="50 req/day",
        max_tokens=32768
    ),
    "openrouter:microsoft/phi-3-medium-128k-instruct": ModelConfig(
        id="openrouter:microsoft/phi-3-medium-128k-instruct",
        name="Phi-3 Medium 128K",
        provider="openrouter",
        api_base="https://openrouter.ai/api/v1",
        free_tier="50 req/day",
        max_tokens=128000
    ),
    # HuggingFace
    "huggingface:HuggingFaceH4/zephyr-7b-beta": ModelConfig(
        id="huggingface:HuggingFaceH4/zephyr-7b-beta",
        name="Zephyr 7B Beta",
        provider="huggingface",
        api_base="https://api-inference.huggingface.co/models",
        free_tier="30 req/day",
        max_tokens=4096
    ),
    "huggingface:berkeley-nest/Starling-LM-7B-alpha": ModelConfig(
        id="huggingface:berkeley-nest/Starling-LM-7B-alpha",
        name="Starling LM 7B Alpha",
        provider="huggingface",
        api_base="https://api-inference.huggingface.co/models",
        free_tier="30 req/day",
        max_tokens=4096
    ),
    # Groq
    "groq:llama3-70b-8192": ModelConfig(
        id="groq:llama3-70b-8192",
        name="Llama 3 70B (Groq)",
        provider="groq",
        api_base="https://api.groq.com/openai/v1",
        free_tier="14400 req/day",
        max_tokens=8192
    ),
    "groq:mixtral-8x7b-32768": ModelConfig(
        id="groq:mixtral-8x7b-32768",
        name="Mixtral 8x7B (Groq)",
        provider="groq",
        api_base="https://api.groq.com/openai/v1",
        free_tier="14400 req/day",
        max_tokens=32768
    ),
    # Ollama (local)
    "ollama:llama3.1:8b": ModelConfig(
        id="ollama:llama3.1:8b",
        name="Llama 3.1 8B (Local)",
        provider="ollama",
        api_base="http://localhost:11434",
        requires_key=False,
        free_tier="Unlimited (local)",
        max_tokens=8192
    ),
    "ollama:mistral:7b": ModelConfig(
        id="ollama:mistral:7b",
        name="Mistral 7B (Local)",
        provider="ollama",
        api_base="http://localhost:11434",
        requires_key=False,
        free_tier="Unlimited (local)",
        max_tokens=8192
    ),
    "ollama:qwen2.5:7b": ModelConfig(
        id="ollama:qwen2.5:7b",
        name="Qwen 2.5 7B (Local)",
        provider="ollama",
        api_base="http://localhost:11434",
        requires_key=False,
        free_tier="Unlimited (local)",
        max_tokens=8192
    ),
}


@dataclass
class EnhancementRequest:
    """Request for idea enhancement."""
    idea: str
    evidence: List[Dict[str, Any]]
    model_id: str
    temperature: float = 0.3
    max_tokens: int = 2048
    stream: bool = False


@dataclass
class EnhancementResponse:
    """Response from enhancement model."""
    model_id: str
    output: EnhancementOutput
    latency_ms: int
    tokens_used: int
    cost_estimate: float
    cached: bool = False
    error: Optional[str] = None


class ModelProvider(ABC):
    """Abstract base class for model providers."""

    @abstractmethod
    async def enhance(self, request: EnhancementRequest, api_key: Optional[str]) -> EnhancementResponse:
        """Generate enhancement for the given request."""
        pass

    @abstractmethod
    async def validate_key(self, api_key: str) -> bool:
        """Validate an API key."""
        pass

    @abstractmethod
    def get_config(self) -> ModelConfig:
        """Get model configuration."""
        pass


class GeminiProvider(ModelProvider):
    """Google Gemini provider."""

    def __init__(self, model_id: str):
        self.model_id = model_id
        self.config = MODEL_REGISTRY[model_id]

    def get_config(self) -> ModelConfig:
        return self.config

    async def validate_key(self, api_key: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.config.api_base}/models?key={api_key}"
                )
                return resp.status_code == 200
        except Exception:
            return False

    async def enhance(self, request: EnhancementRequest, api_key: Optional[str]) -> EnhancementResponse:
        if not api_key:
            return EnhancementResponse(
                model_id=request.model_id,
                output=EnhancementOutput(),
                latency_ms=0,
                tokens_used=0,
                cost_estimate=0.0,
                error="No API key provided for Gemini"
            )

        start_time = time.time()
        
        prompt = self._build_prompt(request.idea, request.evidence)
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{self.config.api_base}/models/{self.config.id}:generateContent?key={api_key}",
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {
                            "temperature": request.temperature,
                            "maxOutputTokens": request.max_tokens,
                            "responseMimeType": "application/json"
                        }
                    }
                )
                
                latency = int((time.time() - start_time) * 1000)
                
                if resp.status_code != 200:
                    return EnhancementResponse(
                        model_id=request.model_id,
                        output=EnhancementOutput(),
                        latency_ms=latency,
                        tokens_used=0,
                        cost_estimate=0.0,
                        error=f"Gemini API error: {resp.status_code}"
                    )
                
                data = resp.json()
                text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                
                # Parse JSON response
                try:
                    output_data = json.loads(text)
                    output = EnhancementOutput(**output_data)
                except json.JSONDecodeError:
                    output = EnhancementOutput(
                        differentiation_angles=[{"angle": "Parse error", "explanation": text}],
                        technical_gaps=[],
                        risk_assessment={},
                        next_steps=[],
                        citations=[]
                    )
                
                return EnhancementResponse(
                    model_id=request.model_id,
                    output=output,
                    latency_ms=latency,
                    tokens_used=data.get("usageMetadata", {}).get("totalTokenCount", 0),
                    cost_estimate=0.0
                )
                
        except Exception as e:
            return EnhancementResponse(
                model_id=request.model_id,
                output=EnhancementOutput(),
                latency_ms=int((time.time() - start_time) * 1000),
                tokens_used=0,
                cost_estimate=0.0,
                error=str(e)
            )

    def _build_prompt(self, idea: str, evidence: List[Dict]) -> str:
        evidence_text = "\n\n".join([
            f"Source: {e.get('source_provider', 'Unknown')}\n"
            f"Title: {e.get('title', 'Unknown')}\n"
            f"Description: {e.get('description', 'No description')}\n"
            f"Shared Concepts: {', '.join(e.get('shared_concepts', []))}"
            for e in evidence[:5]
        ])
        
        return f"""You are an expert engineering research advisor. Analyze the following project idea against the retrieved prior art and provide structured enhancement suggestions.

**Project Idea:**
{idea}

**Retrieved Prior Art (Top Matches):**
{evidence_text}

**Instructions:**
Provide a JSON response with the following structure:
{{
  "differentiation_angles": [
    {{"angle": "string", "explanation": "string", "confidence": "high|medium|low"}}
  ],
  "technical_gaps": [
    {{"gap": "string", "severity": "high|medium|low", "suggestion": "string"}}
  ],
  "risk_assessment": {{
    "novelty_risk": "high|medium|low",
    "feasibility_risk": "high|medium|low",
    "competition_risk": "high|medium|low"
  }},
  "next_steps": [
    {{"step": "string", "priority": "high|medium|low", "rationale": "string"}}
  ],
  "citations": [
    {{"title": "string", "source": "string", "relevance": "string"}}
  ]
}}

Focus on practical, actionable insights for an engineering student. Be specific and evidence-grounded."""


class OpenRouterProvider(ModelProvider):
    """OpenRouter provider for multiple models."""

    def __init__(self, model_id: str):
        self.model_id = model_id
        self.config = MODEL_REGISTRY[model_id]

    def get_config(self) -> ModelConfig:
        return self.config

    async def validate_key(self, api_key: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://openrouter.ai/api/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"}
                )
                return resp.status_code == 200
        except Exception:
            return False

    async def enhance(self, request: EnhancementRequest, api_key: Optional[str]) -> EnhancementResponse:
        if not api_key:
            return EnhancementResponse(
                model_id=request.model_id,
                output=EnhancementOutput(),
                latency_ms=0,
                tokens_used=0,
                cost_estimate=0.0,
                error="No API key provided for OpenRouter"
            )

        start_time = time.time()
        model_name = self.config.id.split(":", 1)[1]
        
        prompt = self._build_prompt(request.idea, request.evidence)
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://idea-enhancer.local",
                        "X-Title": "Idea Enhancer"
                    },
                    json={
                        "model": model_name,
                        "messages": [
                            {"role": "system", "content": "You are an expert engineering research advisor. Respond only with valid JSON."},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": request.temperature,
                        "max_tokens": request.max_tokens,
                        "response_format": {"type": "json_object"}
                    }
                )
                
                latency = int((time.time() - start_time) * 1000)
                
                if resp.status_code != 200:
                    return EnhancementResponse(
                        model_id=request.model_id,
                        output=EnhancementOutput(),
                        latency_ms=latency,
                        tokens_used=0,
                        cost_estimate=0.0,
                        error=f"OpenRouter error: {resp.status_code}"
                    )
                
                data = resp.json()
                text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                
                try:
                    output_data = json.loads(text)
                    output = EnhancementOutput(**output_data)
                except json.JSONDecodeError:
                    output = EnhancementOutput(
                        differentiation_angles=[{"angle": "Parse error", "explanation": text}],
                        technical_gaps=[],
                        risk_assessment={},
                        next_steps=[],
                        citations=[]
                    )
                
                usage = data.get("usage", {})
                return EnhancementResponse(
                    model_id=request.model_id,
                    output=output,
                    latency_ms=latency,
                    tokens_used=usage.get("total_tokens", 0),
                    cost_estimate=0.0
                )
                
        except Exception as e:
            return EnhancementResponse(
                model_id=request.model_id,
                output=EnhancementOutput(),
                latency_ms=int((time.time() - start_time) * 1000),
                tokens_used=0,
                cost_estimate=0.0,
                error=str(e)
            )

    def _build_prompt(self, idea: str, evidence: List[Dict]) -> str:
        evidence_text = "\n\n".join([
            f"Source: {e.get('source_provider', 'Unknown')}\n"
            f"Title: {e.get('title', 'Unknown')}\n"
            f"Description: {e.get('description', 'No description')}\n"
            f"Shared Concepts: {', '.join(e.get('shared_concepts', []))}"
            for e in evidence[:5]
        ])
        
        return f"""You are an expert engineering research advisor. Analyze the following project idea against the retrieved prior art and provide structured enhancement suggestions.

**Project Idea:**
{idea}

**Retrieved Prior Art (Top Matches):**
{evidence_text}

**Instructions:**
Provide a JSON response with the following structure:
{{
  "differentiation_angles": [
    {{"angle": "string", "explanation": "string", "confidence": "high|medium|low"}}
  ],
  "technical_gaps": [
    {{"gap": "string", "severity": "high|medium|low", "suggestion": "string"}}
  ],
  "risk_assessment": {{
    "novelty_risk": "high|medium|low",
    "feasibility_risk": "high|medium|low",
    "competition_risk": "high|medium|low"
  }},
  "next_steps": [
    {{"step": "string", "priority": "high|medium|low", "rationale": "string"}}
  ],
  "citations": [
    {{"title": "string", "source": "string", "relevance": "string"}}
  ]
}}

Focus on practical, actionable insights for an engineering student. Be specific and evidence-grounded."""


class HuggingFaceProvider(ModelProvider):
    """HuggingFace Inference API provider."""

    def __init__(self, model_id: str):
        self.model_id = model_id
        self.config = MODEL_REGISTRY[model_id]

    def get_config(self) -> ModelConfig:
        return self.config

    async def validate_key(self, api_key: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://huggingface.co/api/whoami",
                    headers={"Authorization": f"Bearer {api_key}"}
                )
                return resp.status_code == 200
        except Exception:
            return False

    async def enhance(self, request: EnhancementRequest, api_key: Optional[str]) -> EnhancementResponse:
        if not api_key:
            return EnhancementResponse(
                model_id=request.model_id,
                output=EnhancementOutput(),
                latency_ms=0,
                tokens_used=0,
                cost_estimate=0.0,
                error="No API key provided for HuggingFace"
            )

        start_time = time.time()
        model_name = self.config.id.split(":", 1)[1]
        
        prompt = self._build_prompt(request.idea, request.evidence)
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{self.config.api_base}/{model_name}",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "inputs": prompt,
                        "parameters": {
                            "temperature": request.temperature,
                            "max_new_tokens": request.max_tokens,
                            "return_full_text": False
                        }
                    }
                )
                
                latency = int((time.time() - start_time) * 1000)
                
                if resp.status_code != 200:
                    return EnhancementResponse(
                        model_id=request.model_id,
                        output=EnhancementOutput(),
                        latency_ms=latency,
                        tokens_used=0,
                        cost_estimate=0.0,
                        error=f"HuggingFace error: {resp.status_code}"
                    )
                
                data = resp.json()
                if isinstance(data, list) and data:
                    text = data[0].get("generated_text", "")
                else:
                    text = str(data)
                
                try:
                    output_data = json.loads(text)
                    output = EnhancementOutput(**output_data)
                except json.JSONDecodeError:
                    output = EnhancementOutput(
                        differentiation_angles=[{"angle": "Parse error", "explanation": text}],
                        technical_gaps=[],
                        risk_assessment={},
                        next_steps=[],
                        citations=[]
                    )
                
                return EnhancementResponse(
                    model_id=request.model_id,
                    output=output,
                    latency_ms=latency,
                    tokens_used=0,
                    cost_estimate=0.0
                )
                
        except Exception as e:
            return EnhancementResponse(
                model_id=request.model_id,
                output=EnhancementOutput(),
                latency_ms=int((time.time() - start_time) * 1000),
                tokens_used=0,
                cost_estimate=0.0,
                error=str(e)
            )

    def _build_prompt(self, idea: str, evidence: List[Dict]) -> str:
        evidence_text = "\n\n".join([
            f"Source: {e.get('source_provider', 'Unknown')}\n"
            f"Title: {e.get('title', 'Unknown')}\n"
            f"Description: {e.get('description', 'No description')}\n"
            f"Shared Concepts: {', '.join(e.get('shared_concepts', []))}"
            for e in evidence[:5]
        ])
        
        return f"""<|system|>
You are an expert engineering research advisor. Respond only with valid JSON.<|end|>
<|user|>
Analyze the following project idea against the retrieved prior art and provide structured enhancement suggestions.

**Project Idea:**
{idea}

**Retrieved Prior Art (Top Matches):**
{evidence_text}

**Instructions:**
Provide a JSON response with the following structure:
{{
  "differentiation_angles": [
    {{"angle": "string", "explanation": "string", "confidence": "high|medium|low"}}
  ],
  "technical_gaps": [
    {{"gap": "string", "severity": "high|medium|low", "suggestion": "string"}}
  ],
  "risk_assessment": {{
    "novelty_risk": "high|medium|low",
    "feasibility_risk": "high|medium|low",
    "competition_risk": "high|medium|low"
  }},
  "next_steps": [
    {{"step": "string", "priority": "high|medium|low", "rationale": "string"}}
  ],
  "citations": [
    {{"title": "string", "source": "string", "relevance": "string"}}
  ]
}}

Focus on practical, actionable insights for an engineering student. Be specific and evidence-grounded.
<|end|>
<|assistant|>"""


class GroqProvider(ModelProvider):
    """Groq provider (OpenAI-compatible)."""

    def __init__(self, model_id: str):
        self.model_id = model_id
        self.config = MODEL_REGISTRY[model_id]

    def get_config(self) -> ModelConfig:
        return self.config

    async def validate_key(self, api_key: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"}
                )
                return resp.status_code == 200
        except Exception:
            return False

    async def enhance(self, request: EnhancementRequest, api_key: Optional[str]) -> EnhancementResponse:
        if not api_key:
            return EnhancementResponse(
                model_id=request.model_id,
                output=EnhancementOutput(),
                latency_ms=0,
                tokens_used=0,
                cost_estimate=0.0,
                error="No API key provided for Groq"
            )

        start_time = time.time()
        model_name = self.config.id.split(":", 1)[1]
        
        prompt = self._build_prompt(request.idea, request.evidence)
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": model_name,
                        "messages": [
                            {"role": "system", "content": "You are an expert engineering research advisor. Respond only with valid JSON."},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": request.temperature,
                        "max_tokens": request.max_tokens,
                        "response_format": {"type": "json_object"}
                    }
                )
                
                latency = int((time.time() - start_time) * 1000)
                
                if resp.status_code != 200:
                    return EnhancementResponse(
                        model_id=request.model_id,
                        output=EnhancementOutput(),
                        latency_ms=latency,
                        tokens_used=0,
                        cost_estimate=0.0,
                        error=f"Groq error: {resp.status_code}"
                    )
                
                data = resp.json()
                text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                
                try:
                    output_data = json.loads(text)
                    output = EnhancementOutput(**output_data)
                except json.JSONDecodeError:
                    output = EnhancementOutput(
                        differentiation_angles=[{"angle": "Parse error", "explanation": text}],
                        technical_gaps=[],
                        risk_assessment={},
                        next_steps=[],
                        citations=[]
                    )
                
                usage = data.get("usage", {})
                return EnhancementResponse(
                    model_id=request.model_id,
                    output=output,
                    latency_ms=latency,
                    tokens_used=usage.get("total_tokens", 0),
                    cost_estimate=0.0
                )
                
        except Exception as e:
            return EnhancementResponse(
                model_id=request.model_id,
                output=EnhancementOutput(),
                latency_ms=int((time.time() - start_time) * 1000),
                tokens_used=0,
                cost_estimate=0.0,
                error=str(e)
            )

    def _build_prompt(self, idea: str, evidence: List[Dict]) -> str:
        evidence_text = "\n\n".join([
            f"Source: {e.get('source_provider', 'Unknown')}\n"
            f"Title: {e.get('title', 'Unknown')}\n"
            f"Description: {e.get('description', 'No description')}\n"
            f"Shared Concepts: {', '.join(e.get('shared_concepts', []))}"
            for e in evidence[:5]
        ])
        
        return f"""You are an expert engineering research advisor. Analyze the following project idea against the retrieved prior art and provide structured enhancement suggestions.

**Project Idea:**
{idea}

**Retrieved Prior Art (Top Matches):**
{evidence_text}

**Instructions:**
Provide a JSON response with the following structure:
{{
  "differentiation_angles": [
    {{"angle": "string", "explanation": "string", "confidence": "high|medium|low"}}
  ],
  "technical_gaps": [
    {{"gap": "string", "severity": "high|medium|low", "suggestion": "string"}}
  ],
  "risk_assessment": {{
    "novelty_risk": "high|medium|low",
    "feasibility_risk": "high|medium|low",
    "competition_risk": "high|medium|low"
  }},
  "next_steps": [
    {{"step": "string", "priority": "high|medium|low", "rationale": "string"}}
  ],
  "citations": [
    {{"title": "string", "source": "string", "relevance": "string"}}
  ]
}}

Focus on practical, actionable insights for an engineering student. Be specific and evidence-grounded."""


class OllamaProvider(ModelProvider):
    """Local Ollama provider."""

    def __init__(self, model_id: str):
        self.model_id = model_id
        self.config = MODEL_REGISTRY[model_id]

    def get_config(self) -> ModelConfig:
        return self.config

    async def validate_key(self, api_key: str) -> bool:
        # No key needed for Ollama, just check if server is running
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.config.api_base}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False

    async def enhance(self, request: EnhancementRequest, api_key: Optional[str]) -> EnhancementResponse:
        start_time = time.time()
        model_name = self.config.id.split(":", 1)[1]
        
        prompt = self._build_prompt(request.idea, request.evidence)
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{self.config.api_base}/api/generate",
                    json={
                        "model": model_name,
                        "prompt": prompt,
                        "stream": False,
                        "format": "json",
                        "options": {
                            "temperature": request.temperature,
                            "num_predict": request.max_tokens
                        }
                    }
                )
                
                latency = int((time.time() - start_time) * 1000)
                
                if resp.status_code != 200:
                    return EnhancementResponse(
                        model_id=request.model_id,
                        output=EnhancementOutput(),
                        latency_ms=latency,
                        tokens_used=0,
                        cost_estimate=0.0,
                        error=f"Ollama error: {resp.status_code}"
                    )
                
                data = resp.json()
                text = data.get("response", "")
                
                try:
                    output_data = json.loads(text)
                    output = EnhancementOutput(**output_data)
                except json.JSONDecodeError:
                    output = EnhancementOutput(
                        differentiation_angles=[{"angle": "Parse error", "explanation": text}],
                        technical_gaps=[],
                        risk_assessment={},
                        next_steps=[],
                        citations=[]
                    )
                
                return EnhancementResponse(
                    model_id=request.model_id,
                    output=output,
                    latency_ms=latency,
                    tokens_used=data.get("eval_count", 0),
                    cost_estimate=0.0
                )
                
        except Exception as e:
            return EnhancementResponse(
                model_id=request.model_id,
                output=EnhancementOutput(),
                latency_ms=int((time.time() - start_time) * 1000),
                tokens_used=0,
                cost_estimate=0.0,
                error=str(e)
            )

    def _build_prompt(self, idea: str, evidence: List[Dict]) -> str:
        evidence_text = "\n\n".join([
            f"Source: {e.get('source_provider', 'Unknown')}\n"
            f"Title: {e.get('title', 'Unknown')}\n"
            f"Description: {e.get('description', 'No description')}\n"
            f"Shared Concepts: {', '.join(e.get('shared_concepts', []))}"
            for e in evidence[:5]
        ])
        
        return f"""You are an expert engineering research advisor. Analyze the following project idea against the retrieved prior art and provide structured enhancement suggestions.

**Project Idea:**
{idea}

**Retrieved Prior Art (Top Matches):**
{evidence_text}

**Instructions:**
Provide a JSON response with the following structure:
{{
  "differentiation_angles": [
    {{"angle": "string", "explanation": "string", "confidence": "high|medium|low"}}
  ],
  "technical_gaps": [
    {{"gap": "string", "severity": "high|medium|low", "suggestion": "string"}}
  ],
  "risk_assessment": {{
    "novelty_risk": "high|medium|low",
    "feasibility_risk": "high|medium|low",
    "competition_risk": "high|medium|low"
  }},
  "next_steps": [
    {{"step": "string", "priority": "high|medium|low", "rationale": "string"}}
  ],
  "citations": [
    {{"title": "string", "source": "string", "relevance": "string"}}
  ]
}}

Focus on practical, actionable insights for an engineering student. Be specific and evidence-grounded. Respond only with valid JSON."""


def get_provider(model_id: str) -> ModelProvider:
    """Factory to get provider instance for a model."""
    config = MODEL_REGISTRY.get(model_id)
    if not config:
        raise ValueError(f"Unknown model: {model_id}")
    
    provider_map = {
        "gemini": GeminiProvider,
        "openrouter": OpenRouterProvider,
        "huggingface": HuggingFaceProvider,
        "groq": GroqProvider,
        "ollama": OllamaProvider,
    }
    
    provider_class = provider_map.get(config.provider)
    if not provider_class:
        raise ValueError(f"No provider for: {config.provider}")
    
    return provider_class(model_id)


@dataclass
class CachedEnhancement:
    """Cached enhancement result."""
    response: EnhancementResponse
    timestamp: float
    query_hash: str
    model_id: str
    evidence_hash: str


class MultiModelEnhancer:
    """Orchestrates multi-model enhancement with caching and fallback."""

    def __init__(self):
        self._cache: Dict[str, CachedEnhancement] = {}
        self._cache_ttl = 3600  # 1 hour
        self._max_cache_size = 100

    def _make_cache_key(self, idea: str, model_id: str, evidence: List[Dict]) -> str:
        evidence_str = json.dumps(evidence, sort_keys=True)
        combined = f"{idea}:{model_id}:{evidence_str}"
        return hashlib.sha256(combined.encode()).hexdigest()[:32]

    def _is_cache_valid(self, cached: CachedEnhancement) -> bool:
        return (time.time() - cached.timestamp) < self._cache_ttl

    async def enhance(
        self,
        idea: str,
        evidence: List[Dict],
        model_id: str,
        api_keys: Dict[str, str],
        fallback_chain: Optional[List[str]] = None,
        temperature: float = 0.3,
        max_tokens: int = 2048
    ) -> EnhancementResponse:
        """
        Enhance idea with fallback chain.
        
        Tries primary model, then falls back through chain on error/quota.
        """
        cache_key = self._make_cache_key(idea, model_id, evidence)
        
        # Check cache
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            if self._is_cache_valid(cached):
                cached.response.cached = True
                return cached.response
        
        # Get provider
        try:
            provider = get_provider(model_id)
        except ValueError as e:
            return EnhancementResponse(
                model_id=model_id,
                output=EnhancementOutput(),
                latency_ms=0,
                tokens_used=0,
                cost_estimate=0.0,
                error=str(e)
            )
        
        # Get API key for provider
        config = provider.get_config()
        api_key = api_keys.get(config.provider)
        
        if config.requires_key and not api_key:
            # Try fallback chain
            if fallback_chain:
                for fallback_model in fallback_chain:
                    if fallback_model != model_id:
                        return await self.enhance(
                            idea, evidence, fallback_model, api_keys,
                            fallback_chain=None, temperature=0.3, max_tokens=2048
                        )
            return EnhancementResponse(
                model_id=model_id,
                output=EnhancementOutput(),
                latency_ms=0,
                tokens_used=0,
                cost_estimate=0.0,
                error=f"No API key for {config.provider}"
            )
        
        # Execute enhancement
        request = EnhancementRequest(
            idea=idea,
            evidence=evidence,
            model_id=model_id,
            temperature=0.3,
            max_tokens=2048
        )
        
        response = await provider.enhance(request, api_key)
        
        # Cache successful responses
        if not response.error:
            # Manage cache size
            if len(self._cache) >= self._max_cache_size:
                # Remove oldest
                oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k].timestamp)
                del self._cache[oldest_key]
            
            self._cache[cache_key] = CachedEnhancement(
                response=response,
                timestamp=time.time(),
                query_hash=hashlib.sha256(idea.encode()).hexdigest()[:16],
                model_id=model_id,
                evidence_hash=hashlib.sha256(json.dumps(evidence, sort_keys=True).encode()).hexdigest()[:16]
            )
        
        return response

    async def compare_models(
        self,
        idea: str,
        evidence: List[Dict],
        model_ids: List[str],
        api_keys: Dict[str, str]
    ) -> Dict[str, EnhancementResponse]:
        """Run enhancement with multiple models for comparison."""
        tasks = [
            self.enhance(idea, evidence, model_id, api_keys)
            for model_id in model_ids
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return {
            model_id: result if not isinstance(result, Exception) 
            else EnhancementResponse(
                model_id=model_id,
                output=EnhancementOutput(),
                latency_ms=0,
                tokens_used=0,
                cost_estimate=0.0,
                error=str(result)
            )
            for model_id, result in zip(model_ids, results)
        }

    def clear_cache(self):
        """Clear the enhancement cache."""
        self._cache.clear()