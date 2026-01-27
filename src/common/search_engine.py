"""
Search engine abstraction layer.
Supports DuckDuckGo and SearXNG backends.
"""
import time
import requests
from typing import List, Dict, Optional
from common.config import settings


class SearchEngine:
    """Base class for search engines."""
    
    def search(self, query: str, max_results: int = 10) -> List[Dict]:
        """
        Search for a query and return results.
        
        Returns:
            List of dicts with keys: url, title, snippet
        """
        raise NotImplementedError


class DuckDuckGoSearch(SearchEngine):
    """DuckDuckGo search implementation."""
    
    def search(self, query: str, max_results: int = 10) -> List[Dict]:
        from duckduckgo_search import DDGS
        
        results = []
        try:
            with DDGS() as ddgs:
                search_results = list(ddgs.text(query, max_results=max_results))
                
            for r in search_results:
                results.append({
                    "url": r.get("href", ""),
                    "title": r.get("title", ""),
                    "snippet": r.get("body", ""),
                })
        except Exception as e:
            print(f"❌ DuckDuckGo search error: {e}")
        
        return results


class SearXNGSearch(SearchEngine):
    """SearXNG search implementation."""
    
    def __init__(self, base_url: str):
        """
        Initialize SearXNG client.
        
        Args:
            base_url: SearXNG instance URL (e.g., http://localhost:8080)
        """
        self.base_url = base_url.rstrip("/")
        self.search_endpoint = f"{self.base_url}/search"
    
    def search(self, query: str, max_results: int = 10) -> List[Dict]:
        """
        Search using SearXNG API.
        
        Note: SearXNG must have JSON format enabled in settings.yml:
            search:
              formats:
                - html
                - json
        """
        results = []
        
        params = {
            "q": query,
            "format": "json",
            "categories": "general",
            "language": "auto",
            "safesearch": 0,
            "pageno": 1,
        }
        
        headers = {
            "Accept": "application/json",
            "User-Agent": "AI-Agent-Search-Worker/1.0",
        }
        
        try:
            response = requests.get(
                self.search_endpoint,
                params=params,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            search_results = data.get("results", [])[:max_results]
            
            for r in search_results:
                results.append({
                    "url": r.get("url", ""),
                    "title": r.get("title", ""),
                    "snippet": r.get("content", ""),
                })
            
            print(f"✅ SearXNG returned {len(results)} results")
            
        except requests.exceptions.RequestException as e:
            print(f"❌ SearXNG request error: {e}")
        except ValueError as e:
            print(f"❌ SearXNG JSON parse error: {e}")
            print("💡 Tip: Make sure JSON format is enabled in SearXNG settings.yml")
        
        return results


def get_search_engine() -> SearchEngine:
    """
    Factory function to get the configured search engine.
    
    Returns:
        SearchEngine instance based on SEARCH_ENGINE setting
    """
    engine = settings.SEARCH_ENGINE.lower()
    
    if engine == "searxng":
        if not settings.SEARXNG_URL:
            print("⚠️  SEARXNG_URL not set, falling back to DuckDuckGo")
            return DuckDuckGoSearch()
        print(f"🔍 Using SearXNG at {settings.SEARXNG_URL}")
        return SearXNGSearch(settings.SEARXNG_URL)
    else:
        print("🔍 Using DuckDuckGo Search")
        return DuckDuckGoSearch()
