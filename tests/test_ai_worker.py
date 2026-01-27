"""
Unit tests for AI Worker utility functions.
Tests GPU memory detection and model selection logic.
"""
import pytest
from unittest.mock import patch, MagicMock
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Import functions to test (safe - no heavy dependencies like vLLM)
from common.ai_worker_utils import get_gpu_memory_gb, select_model_by_vram


class TestGetGpuMemoryGb:
    """Tests for GPU memory detection function."""
    
    def test_nvidia_smi_success(self):
        """Test GPU memory detection via nvidia-smi."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="12288\n"  # 12GB in MB
            )
            
            result = get_gpu_memory_gb()
            assert result == 12.0
    
    def test_nvidia_smi_24gb(self):
        """Test detection of 24GB GPU."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="24576\n"  # 24GB in MB
            )
            
            result = get_gpu_memory_gb()
            assert result == 24.0
    
    def test_nvidia_smi_failure_returns_none(self):
        """Test fallback when nvidia-smi fails and pynvml not available."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError("nvidia-smi not found")
            
            # Also mock pynvml import to fail
            with patch.dict('sys.modules', {'pynvml': None}):
                result = get_gpu_memory_gb()
                assert result is None


class TestSelectModelByVram:
    """Tests for model selection based on VRAM."""
    
    def test_24gb_plus_selects_70b(self):
        """Test model selection for 24GB+ GPUs."""
        model, quant, max_len = select_model_by_vram(24.0)
        
        assert "70B" in model
        assert quant == "awq"
        assert max_len == 8192
    
    def test_48gb_selects_70b(self):
        """Test model selection for high-end GPUs."""
        model, quant, max_len = select_model_by_vram(48.0)
        
        assert "70B" in model
        assert max_len == 8192
    
    def test_12gb_selects_8b_long_context(self):
        """Test model selection for 12GB GPUs."""
        model, quant, max_len = select_model_by_vram(12.0)
        
        assert "8B" in model
        assert quant == "awq"
        assert max_len == 8192  # Full context for 12GB
    
    def test_8gb_selects_8b_medium_context(self):
        """Test model selection for 8GB GPUs."""
        model, quant, max_len = select_model_by_vram(8.0)
        
        assert "8B" in model
        assert max_len == 4096  # Reduced context
    
    def test_6gb_selects_8b_medium_context(self):
        """Test model selection for 6GB GPUs."""
        model, quant, max_len = select_model_by_vram(6.0)
        
        assert "8B" in model
        assert max_len == 4096
    
    def test_4gb_selects_8b_short_context(self):
        """Test model selection for low VRAM GPUs."""
        model, quant, max_len = select_model_by_vram(4.0)
        
        assert "8B" in model
        assert max_len == 2048  # Minimum context for low VRAM
    
    def test_boundary_20gb(self):
        """Test 20GB boundary selects 70B model."""
        model, _, _ = select_model_by_vram(20.0)
        assert "70B" in model
    
    def test_boundary_10gb(self):
        """Test 10GB boundary selects 8B with full context."""
        model, _, max_len = select_model_by_vram(10.0)
        assert "8B" in model
        assert max_len == 8192
