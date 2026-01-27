"""
Pytest configuration and fixtures for AI Agent tests.
"""
import os
import sys
import pytest
from unittest.mock import MagicMock, patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


# ============================================
# Database Fixtures
# ============================================

@pytest.fixture
def mock_db_session():
    """Mock database session for testing."""
    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = None
    session.query.return_value.count.return_value = 0
    return session


@pytest.fixture
def sample_request_data():
    """Sample request data for testing."""
    return {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "topic": "Test topic for analysis",
        "status": "pending",
    }


@pytest.fixture
def sample_search_results():
    """Sample search results for testing."""
    return [
        {
            "url": "https://example.com/article1",
            "title": "Test Article 1",
            "content": "This is test content for article 1.",
        },
        {
            "url": "https://example.com/article2", 
            "title": "Test Article 2",
            "content": "This is test content for article 2.",
        },
    ]


# ============================================
# Kafka Fixtures
# ============================================

@pytest.fixture
def mock_kafka_producer():
    """Mock Kafka producer for testing."""
    with patch('common.utils.KafkaProducer') as mock:
        producer = MagicMock()
        mock.return_value = producer
        yield producer


@pytest.fixture
def mock_kafka_consumer():
    """Mock Kafka consumer for testing."""
    with patch('common.utils.KafkaConsumer') as mock:
        consumer = MagicMock()
        mock.return_value = consumer
        yield consumer
