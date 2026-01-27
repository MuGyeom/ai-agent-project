"""
Unit tests for Search Worker functions.
"""
import pytest
from unittest.mock import patch, MagicMock
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestSearchEngine:
    """Tests for search engine abstraction."""
    
    def test_duckduckgo_search_returns_results(self):
        """Test DuckDuckGo search returns results."""
        from common.search_engine import DuckDuckGoSearch
        
        with patch('duckduckgo_search.DDGS') as mock_ddgs:
            mock_instance = MagicMock()
            mock_ddgs.return_value.__enter__.return_value = mock_instance
            mock_instance.text.return_value = [
                {"href": "https://example.com", "title": "Example", "body": "Description"},
            ]
            
            engine = DuckDuckGoSearch()
            results = engine.search("test query", max_results=1)
            
            assert len(results) == 1
            assert results[0]["url"] == "https://example.com"
            assert results[0]["title"] == "Example"
    
    def test_duckduckgo_handles_empty_results(self):
        """Test DuckDuckGo handles empty results gracefully."""
        from common.search_engine import DuckDuckGoSearch
        
        with patch('duckduckgo_search.DDGS') as mock_ddgs:
            mock_instance = MagicMock()
            mock_ddgs.return_value.__enter__.return_value = mock_instance
            mock_instance.text.return_value = []
            
            engine = DuckDuckGoSearch()
            results = engine.search("nonexistent", max_results=5)
            
            assert results == []
    
    def test_searxng_search_returns_results(self):
        """Test SearXNG search returns results."""
        from common.search_engine import SearXNGSearch
        
        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "results": [
                    {"url": "https://example.com", "title": "Example", "content": "Description"},
                ]
            }
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response
            
            engine = SearXNGSearch("http://localhost:8080")
            results = engine.search("test query", max_results=1)
            
            assert len(results) == 1
            assert results[0]["url"] == "https://example.com"
    
    def test_get_search_engine_default(self):
        """Test default search engine is DuckDuckGo."""
        from common.search_engine import get_search_engine, DuckDuckGoSearch
        
        with patch('common.search_engine.settings') as mock_settings:
            mock_settings.SEARCH_ENGINE = "duckduckgo"
            mock_settings.SEARXNG_URL = None
            
            engine = get_search_engine()
            assert isinstance(engine, DuckDuckGoSearch)
    
    def test_get_search_engine_searxng(self):
        """Test SearXNG engine selection."""
        from common.search_engine import get_search_engine, SearXNGSearch
        
        with patch('common.search_engine.settings') as mock_settings:
            mock_settings.SEARCH_ENGINE = "searxng"
            mock_settings.SEARXNG_URL = "http://localhost:8080"
            
            engine = get_search_engine()
            assert isinstance(engine, SearXNGSearch)


class TestSearchAndCrawl:
    """Tests for search_and_crawl function."""
    
    def test_search_and_crawl_returns_results(self):
        """Test search_and_crawl returns results with content."""
        # Mock dependencies
        with patch('common.utils.KafkaProducer'):
            with patch('common.utils.KafkaConsumer'):
                with patch('common.database.create_engine'):
                    with patch('common.search_engine.get_search_engine') as mock_engine:
                        mock_search = MagicMock()
                        mock_search.search.return_value = [
                            {"url": "https://example.com", "title": "Example", "snippet": "Test"}
                        ]
                        mock_engine.return_value = mock_search
                        
                        with patch('trafilatura.fetch_url') as mock_fetch:
                            mock_fetch.return_value = "<html><body>Content</body></html>"
                            
                            with patch('trafilatura.extract') as mock_extract:
                                # Return content > 100 chars
                                mock_extract.return_value = "A" * 150
                                
                                with patch('time.sleep'):
                                    from search_worker.main import search_and_crawl
                                    results = search_and_crawl("test", max_results=1)
                                    
                                    assert len(results) >= 1
                                    assert results[0]["url"] == "https://example.com"
