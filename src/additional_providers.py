"""Additional free API providers for live search."""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

from src.live_search.contracts import CandidateRecord
from src.live_search.http import ProviderFailure, get_json
from src.live_search.providers import (
    _candidate_id,
    _clean_text,
    _safe_url,
    _SPACE,
)

logger = logging.getLogger(__name__)


@dataclass
class SemanticScholarProvider:
    """Semantic Scholar API provider."""
    name = "semantic_scholar"
    endpoint = "https://api.semanticscholar.org/graph/v1"

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key

    async def search(
        self,
        idea: str,
        client: httpx.AsyncClient,
        limit: int = 20
    ) -> Dict[str, Any]:
        """Search Semantic Scholar for papers."""
        bounded_limit = min(max(int(limit), 1), 100)
        
        # Build query
        query = _SPACE.sub(" ", idea).strip()[:512]
        
        params = {
            "query": query,
            "limit": bounded_limit,
            "fields": "paperId,title,abstract,venue,year,publicationTypes,citationCount,influentialCitationCount,authors,externalIds,url,openAccessPdf"
        }
        
        headers = {"User-Agent": "IdeaEnhancer/1.0 (student research discovery)"}
        if self._api_key:
            headers["x-api-key"] = self._api_key
        
        try:
            payload = await get_json(
                client,
                f"{self.endpoint}/paper/search",
                params=params,
                headers=headers
            )
        except ProviderFailure as error:
            return {"state": "failed", "error": str(error), "candidates": []}
        
        papers = payload.get("data", [])
        if not isinstance(papers, list):
            return {"state": "invalid_response", "candidates": []}
        
        candidates: List[CandidateRecord] = []
        for paper in papers[:bounded_limit]:
            if not isinstance(paper, dict):
                continue
            
            paper_id = _clean_text(paper.get("paperId"), 512)
            title = _clean_text(paper.get("title"), 2000)
            if not paper_id or not title:
                continue
            
            abstract = _clean_text(paper.get("abstract"), 12000)
            venue = _clean_text(paper.get("venue"), 500)
            year = paper.get("year")
            if isinstance(year, int) and 1000 <= year <= 9999:
                year_str = str(year)
            else:
                year_str = None
            
            authors = []
            for author in paper.get("authors", [])[:20]:
                if isinstance(author, dict):
                    name = _clean_text(author.get("name"), 300)
                    if name:
                        authors.append(name)
            
            # Get DOI from externalIds
            doi = None
            external_ids = paper.get("externalIds", {})
            if isinstance(external_ids, dict):
                doi = _clean_text(external_ids.get("DOI"), 512)
            
            # Get URL
            source_url = _safe_url(
                paper.get("url") or 
                (f"https://www.semanticscholar.org/paper/{paper_id}" if paper_id else None) or
                (f"https://doi.org/{doi}" if doi else None)
            )
            
            candidates.append(CandidateRecord(
                candidate_id=_candidate_id(self.name, paper_id),
                source_provider=self.name,
                provider_id=paper_id,
                candidate_type="paper",
                title=title,
                description=abstract,
                source_url=source_url,
                doi=doi,
                authors=tuple(authors),
                publication_date=str(year) if year_str else None,
                publication_year=int(year_str) if year_str and year_str.isdigit() else None,
                venue=venue,
                open_access=paper.get("openAccessPdf") is not None,
                citation_count=paper.get("citationCount"),
                influential_citation_count=paper.get("influentialCitationCount")
            ))
        
        if papers and not candidates:
            return {"state": "invalid_records", "candidates": []}
        
        return {"state": "success", "candidates": candidates}

    async def get_citations(
        self,
        paper_id: str,
        client: httpx.AsyncClient,
        limit: int = 50
    ) -> List[CandidateRecord]:
        """Get papers that cite the given paper."""
        params = {
            "limit": min(max(int(limit), 1), 1000),
            "fields": "paperId,title,abstract,venue,year,citationCount,authors,externalIds,url"
        }
        
        headers = {"User-Agent": "IdeaEnhancer/1.0"}
        if self._api_key:
            params["fields"] += ",influentialCitationCount"
        
        try:
            payload = await get_json(
                client,
                f"{self.endpoint}/paper/{paper_id}/citations",
                params=params
            )
        except ProviderFailure:
            return []
        
        return self._parse_papers(payload.get("data", []))
    
    def _parse_papers(self, papers: List[Dict]) -> List[CandidateRecord]:
        candidates = []
        for paper in papers:
            citing_paper = paper.get("citingPaper") or paper.get("citedPaper")
            if not citing_paper:
                continue
            candidates.append(self._paper_to_candidate(citing_paper))
        return [c for c in candidates if c]

    def _paper_to_candidate(self, paper: Dict) -> Optional[CandidateRecord]:
        paper_id = _clean_text(paper.get("paperId"), 512)
        title = _clean_text(paper.get("title"), 2000)
        if not paper_id or not title:
            return None
        
        abstract = _clean_text(paper.get("abstract"), 12000)
        venue = _clean_text(paper.get("venue"), 500)
        year = paper.get("year")
        year_str = str(year) if isinstance(year, int) and 1000 <= year <= 9999 else None
        
        authors = []
        for author in paper.get("authors", [])[:20]:
            if isinstance(author, dict):
                name = _clean_text(author.get("name"), 300)
                if name:
                    authors.append(name)
        
        doi = None
        external_ids = paper.get("externalIds", {})
        if isinstance(external_ids, dict):
            doi = _clean_text(external_ids.get("DOI"), 512)
        
        source_url = _safe_url(
            paper.get("url") or 
            (f"https://www.semanticscholar.org/paper/{paper_id}" if paper_id else None) or
            (f"https://doi.org/{doi}" if doi else None)
        )
        
        return CandidateRecord(
            candidate_id=_candidate_id(self.name, paper_id),
            source_provider=self.name,
            provider_id=paper_id,
            candidate_type="paper",
            title=title,
            description=abstract,
            source_url=source_url,
            doi=doi,
            authors=tuple(authors),
            publication_date=year_str,
            publication_year=int(year_str) if year_str and year_str.isdigit() else None,
            venue=venue,
            citation_count=paper.get("citationCount"),
            influential_citation_count=paper.get("influentialCitationCount")
        )


@dataclass
class ArXivProvider:
    """arXiv API provider."""
    name = "arxiv"
    endpoint = "http://export.arxiv.org/api/query"

    async def search(
        self,
        idea: str,
        client: httpx.AsyncClient,
        limit: int = 20
    ) -> Dict[str, Any]:
        """Search arXiv for preprints."""
        bounded_limit = min(max(int(limit), 1), 200)
        
        # Build search query
        query = _SPACE.sub(" ", idea).strip()[:300]
        # Search in title, abstract, comments
        search_query = f"all:{query}"
        
        params = {
            "search_query": search_query,
            "start": 0,
            "max_results": bounded_limit,
            "sortBy": "relevance",
            "sortOrder": "descending"
        }
        
        try:
            # arXiv returns XML
            resp = await client.get(self.endpoint, params=params, timeout=30.0)
            resp.raise_for_status()
            xml_content = resp.text
        except Exception as e:
            logger.warning("arXiv search failed: %s", e)
            return {"state": "failed", "error": str(e), "candidates": []}
        
        # Parse XML
        candidates = self._parse_arxiv_xml(xml_content, bounded_limit)
        
        if not candidates:
            return {"state": "empty", "candidates": []}
        
        return {"state": "success", "candidates": candidates}

    def _parse_arxiv_xml(self, xml: str, limit: int) -> List[CandidateRecord]:
        import xml.etree.ElementTree as ET
        
        candidates = []
        try:
            root = ET.fromstring(xml)
            # arXiv uses atom namespace
            ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
            
            for entry in root.findall("atom:entry", ns)[:50]:
                try:
                    # Get arXiv ID
                    id_elem = entry.find("atom:id", {"atom": "http://www.w3.org/2005/Atom"})
                    if id_elem is None or not id_elem.text:
                        continue
                    arxiv_url = id_elem.text.strip()
                    arxiv_id = arxiv_url.split("/")[-1]
                    if "v" in arxiv_id:
                        arxiv_id = arxiv_id.split("v")[0]
                    
                    title_elem = entry.find("atom:title", {"atom": "http://www.w3.org/2005/Atom"})
                    title = _clean_text(title_elem.text, 2000) if title_elem is not None and title_elem.text else None
                    if not title:
                        continue
                    
                    summary_elem = entry.find("atom:summary", {"atom": "http://www.w3.org/2005/Atom"})
                    abstract = _clean_text(summary_elem.text, 12000) if summary_elem is not None and summary_elem.text else ""
                    
                    # Published date
                    published_elem = entry.find("atom:published", {"atom": "http://www.w3.org/2005/Atom"})
                    year = None
                    if published_elem is not None and published_elem.text:
                        try:
                            year = int(published_elem.text[:4])
                        except (ValueError, TypeError):
                            pass
                    
                    # Authors
                    authors = []
                    for author_elem in entry.findall("atom:author", {"atom": "http://www.w3.org/2005/Atom"})[:20]:
                        name_elem = author_elem.find("atom:name", {"atom": "http://www.w3.org/2005/Atom"})
                        if name_elem is not None and name_elem.text:
                            name = _clean_text(name_elem.text, 300)
                            if name:
                                authors.append(name)
                    
                    # Categories
                    categories = []
                    for cat_elem in entry.findall("arxiv:primary_category", {"arxiv": "http://arxiv.org/schemas/atom"}):
                        term = cat_elem.get("term")
                        if term:
                            categories.append(term)
                    
                    # Links
                    source_url = f"https://arxiv.org/abs/{arxiv_id}"
                    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
                    
                    candidates.append(CandidateRecord(
                        candidate_id=f"arxiv_{arxiv_id}",
                        source_provider="arxiv",
                        provider_id=arxiv_id,
                        candidate_type="paper",
                        title=title or "Untitled",
                        description=_clean_text(_SPACE.sub(" ", ""), 12000) if not summary_elem else "",
                        source_url=source_url,
                        pdf_url=pdf_url,
                        authors=tuple(authors),
                        publication_year=year,
                        venue="arXiv",
                        categories=tuple(categories)
                    ))
                except Exception as e:
                    logger.debug("Failed to parse arXiv entry: %s", e)
                    continue
        except ET.ParseError as e:
            logger.warning("Failed to parse arXiv XML: %s", e)
        
        return candidates[:50]


@dataclass
class CrossRefProvider:
    """CrossRef API provider for DOI metadata."""
    name = "crossref"
    endpoint = "https://api.crossref.org"

    async def search(
        self,
        idea: str,
        client: httpx.AsyncClient,
        limit: int = 20
    ) -> Dict[str, Any]:
        """Search CrossRef for DOIs."""
        bounded_limit = min(max(int(limit), 1), 100)
        
        query = _SPACE.sub(" ", idea).strip()[:512]
        
        params = {
            "query": query,
            "rows": bounded_limit,
            "select": "DOI,title,abstract,author,container-title,issued,type,publisher,URL,is-referenced-by-count,subject"
        }
        
        headers = {
            "User-Agent": "IdeaEnhancer/1.0 (student research discovery; mailto:student@example.edu)"
        }
        
        try:
            payload = await get_json(
                client,
                f"{self.endpoint}/works",
                params=params,
                headers=headers
            )
        except ProviderFailure as error:
            return {"state": "failed", "error": str(error), "candidates": []}
        
        items = payload.get("message", {}).get("items", [])
        if not isinstance(items, list):
            return {"state": "invalid_response", "candidates": []}
        
        candidates = []
        for item in items[:bounded_limit]:
            if not isinstance(item, dict):
                continue
            
            doi = _clean_text(item.get("DOI"), 512)
            title_list = item.get("title", [])
            title = _clean_text(title_list[0] if title_list else None, 2000)
            if not doi or not title:
                continue
            
            abstract = _clean_text(item.get("abstract"), 12000)
            container = item.get("container-title", [])
            venue = _clean_text(container[0] if container else None, 500)
            
            # Authors
            authors = []
            for author in item.get("author", [])[:20]:
                if isinstance(author, dict):
                    given = _clean_text(author.get("given"), 200)
                    family = _clean_text(author.get("family"), 200)
                    if given or family:
                        authors.append(f"{given} {family}".strip())
            
            # Year
            issued = item.get("issued", {})
            year = None
            if "date-parts" in issued and issued["date-parts"]:
                parts = issued["date-parts"][0]
                if parts and isinstance(parts[0], int):
                    year = parts[0]
            
            # Citation count
            citation_count = item.get("is-referenced-by-count")
            if not isinstance(citation_count, int) or citation_count < 0:
                citation_count = None
            
            # URL
            source_url = _safe_url(item.get("URL") or (f"https://doi.org/{doi}" if doi else None))
            
            candidates.append(CandidateRecord(
                candidate_id=f"crossref_{doi.replace('/', '_')}",
                source_provider="crossref",
                provider_id=doi,
                candidate_type="paper",
                title=title,
                description=abstract,
                source_url=source_url,
                doi=doi,
                authors=tuple(authors),
                publication_date=str(year) if year else None,
                publication_year=year,
                venue=venue,
                citation_count=citation_count,
                type=item.get("type"),
                publisher=item.get("publisher"),
                subject=item.get("subject")
            ))
        
        if items and not candidates:
            return {"state": "invalid_records", "candidates": []}
        
        return {"state": "success", "candidates": candidates}


@dataclass
class COREProvider:
    """CORE API provider for open access papers."""
    name = "core"
    endpoint = "https://api.core.ac.uk/v3"

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key

    async def search(
        self,
        idea: str,
        client: httpx.AsyncClient,
        limit: int = 20
    ) -> Dict[str, Any]:
        """Search CORE for open access papers."""
        bounded_limit = min(max(int(limit), 1), 100)
        
        query = _SPACE.sub(" ", idea).strip()[:512]
        
        params = {
            "q": query,
            "limit": bounded_limit,
            "scroll": "false"
        }
        
        headers = {"User-Agent": "IdeaEnhancer/1.0"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        
        try:
            payload = await get_json(
                client,
                f"{self.endpoint}/search/works",
                params=params,
                headers=headers
            )
        except ProviderFailure as error:
            return {"state": "failed", "error": str(error), "candidates": []}
        
        results = payload.get("results", [])
        if not isinstance(results, list):
            return {"state": "invalid_response", "candidates": []}
        
        candidates = []
        for paper in results[:bounded_limit]:
            if not isinstance(paper, dict):
                continue
            
            core_id = _clean_text(paper.get("id"), 512)
            title = _clean_text(paper.get("title"), 2000)
            if not core_id or not title:
                continue
            
            abstract = _clean_text(paper.get("abstract"), 12000)
            
            # Authors
            authors = []
            for author in paper.get("authors", [])[:20]:
                if isinstance(author, dict):
                    name = _clean_text(author.get("name"), 300)
                    if name:
                        authors.append(name)
                elif isinstance(author, str):
                    name = _clean_text(author, 300)
                    if name:
                        authors.append(name)
            
            # Year
            year = None
            if "yearPublished" in paper and paper["yearPublished"]:
                try:
                    year = int(paper["yearPublished"])
                except (ValueError, TypeError):
                    pass
            
            # Venue
            venue = _clean_text(paper.get("publisher"), 500)
            
            # URLs
            source_url = _safe_url(paper.get("downloadUrl") or paper.get("sourceFulltextUrl") or paper.get("url"))
            pdf_url = _safe_url(paper.get("downloadUrl"))
            
            # DOI
            doi = _clean_text(paper.get("doi"), 512)
            
            candidates.append(CandidateRecord(
                candidate_id=f"core_{core_id}",
                source_provider="core",
                provider_id=core_id,
                candidate_type="paper",
                title=title,
                description=abstract,
                source_url=source_url,
                pdf_url=pdf_url,
                doi=doi,
                authors=tuple(authors),
                publication_date=str(year) if year else None,
                publication_year=year,
                venue=venue,
                open_access=True
            ))
        
        if results and not candidates:
            return {"state": "invalid_records", "candidates": []}
        
        return {"state": "success", "candidates": candidates}


# Registry of additional providers
ADDITIONAL_PROVIDERS = {
    "semantic_scholar": SemanticScholarProvider,
    "arxiv": ArXivProvider,
    "crossref": CrossRefProvider,
    "core": COREProvider,
}


def get_additional_provider(name: str, api_key: Optional[str] = None):
    """Factory to get additional provider instance."""
    provider_class = ADDITIONAL_PROVIDERS.get(name)
    if not provider_class:
        raise ValueError(f"Unknown provider: {name}")
    return provider_class(api_key=api_key)