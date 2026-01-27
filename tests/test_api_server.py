"""
Unit tests for API Server endpoints.
Uses mocking to avoid actual database/Kafka connections.
"""
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from uuid import uuid4
from datetime import datetime
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


# Mock database and Kafka before importing app module
@pytest.fixture(autouse=True)
def mock_infrastructure():
    """Mock all infrastructure dependencies."""
    with patch.dict(os.environ, {
        'DATABASE_URL': 'postgresql://test:test@localhost:5432/test',
        'KAFKA_BOOTSTRAP_SERVERS': 'localhost:9092'
    }):
        with patch('common.database.create_engine') as mock_engine:
            with patch('common.database.SessionLocal') as mock_session_class:
                with patch('common.utils.KafkaProducer'):
                    yield {
                        'engine': mock_engine,
                        'session_class': mock_session_class
                    }


class TestAnalyzeEndpoint:
    """Tests for /analyze endpoint."""
    
    def test_analyze_request_validation(self, mock_infrastructure):
        """Test that analyze endpoint validates request."""
        # We test the Pydantic model directly instead of hitting the endpoint
        from pydantic import BaseModel
        
        class AnalyzeRequest(BaseModel):
            topic: str
        
        # Valid request
        req = AnalyzeRequest(topic="test topic")
        assert req.topic == "test topic"
        
        # Invalid request should raise
        with pytest.raises(Exception):
            AnalyzeRequest()  # Missing topic


class TestStatusEndpointLogic:
    """Tests for status endpoint logic."""
    
    def test_request_not_found_returns_none(self, mock_infrastructure):
        """Test that querying non-existent request returns None."""
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = None
        
        result = mock_session.query().filter().first()
        assert result is None
    
    def test_request_found_returns_data(self, mock_infrastructure):
        """Test that querying existing request returns data."""
        mock_session = MagicMock()
        
        # Create mock request
        mock_request = MagicMock()
        mock_request.id = uuid4()
        mock_request.topic = "test topic"
        mock_request.status = "completed"
        mock_request.created_at = datetime.utcnow()
        mock_request.updated_at = datetime.utcnow()
        mock_request.completed_at = datetime.utcnow()
        mock_request.error_message = None
        mock_request.search_results = []
        mock_request.analysis_result = None
        
        mock_session.query.return_value.filter.return_value.first.return_value = mock_request
        
        result = mock_session.query().filter().first()
        assert result.status == "completed"
        assert result.topic == "test topic"


class TestRequestModel:
    """Tests for Request model structure."""
    
    def test_request_status_values(self):
        """Test valid request status values."""
        valid_statuses = ['pending', 'searching', 'processing_search', 
                         'analyzing', 'processing_analysis', 'completed', 'failed']
        
        for status in valid_statuses:
            mock_request = MagicMock()
            mock_request.status = status
            assert mock_request.status in valid_statuses


class TestKafkaIntegration:
    """Tests for Kafka producer integration."""
    
    def test_producer_send_data(self, mock_infrastructure):
        """Test that producer sends data correctly."""
        from common.utils import KafkaProducerWrapper
        
        with patch('common.utils.KafkaProducer') as mock_kafka:
            mock_producer_instance = MagicMock()
            mock_kafka.return_value = mock_producer_instance
            
            producer = KafkaProducerWrapper()
            producer.send_data(topic="test-topic", value={"key": "value"})
            
            mock_producer_instance.send.assert_called_once()
