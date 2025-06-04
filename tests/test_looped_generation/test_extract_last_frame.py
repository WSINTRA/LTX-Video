import os
import pytest
import tempfile
from unittest.mock import MagicMock, patch, mock_open
import sys
import subprocess

# Add the parent directory to sys.path to import looped_generation directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from looped_generation import extract_last_frame


def test_extract_last_frame_validates_empty_path():
    """Test that extract_last_frame raises ValueError for empty path"""
    with pytest.raises(ValueError, match="Video path cannot be empty"):
        extract_last_frame("")
    
    with pytest.raises(ValueError, match="Video path cannot be empty"):
        extract_last_frame("   ")


def test_extract_last_frame_validates_file_exists():
    """Test that extract_last_frame raises FileNotFoundError for non-existent file"""
    with pytest.raises(FileNotFoundError, match="The video file '/nonexistent/path.mp4' does not exist"):
        extract_last_frame("/nonexistent/path.mp4")


def test_extract_last_frame_sanitizes_path():
    """Test that extract_last_frame properly sanitizes input path"""
    video_path = "  /path/to/video.mp4  "  # Path with whitespace
    
    with patch('subprocess.run') as mock_subprocess, \
         patch('os.path.isfile', return_value=True), \
         patch('looped_generation.logger'):
        
        with pytest.raises(FileNotFoundError):  # Will fail because mocked path doesn't exist
            extract_last_frame(video_path)
        
        # The path should be sanitized (abspath called on stripped path)
        # We can't easily test the exact sanitization without more complex mocking


def test_extract_last_frame_handles_ffmpeg_success():
    """Test that extract_last_frame handles successful FFmpeg execution"""
    video_path = "/path/to/video.mp4"
    expected_png = "/path/to/video_last_frame.png"
    
    mock_result = MagicMock()
    mock_result.stdout = "FFmpeg success output"
    
    with patch('subprocess.run', return_value=mock_result) as mock_subprocess, \
         patch('pathlib.Path.is_file', return_value=True), \
         patch('looped_generation.logger') as mock_logger:
        
        result = extract_last_frame(video_path)
        
        # Check that the correct PNG path is returned
        assert result == expected_png
        
        # Check that FFmpeg was called with correct arguments
        mock_subprocess.assert_called_once()
        call_args = mock_subprocess.call_args[0][0]
        assert "ffmpeg" in call_args
        assert "-sseof" in call_args
        assert "-1" in call_args
        assert video_path in call_args
        assert expected_png in call_args
        
        # Check that logging occurred
        mock_logger.info.assert_called_once()


def test_extract_last_frame_handles_ffmpeg_error():
    """Test that extract_last_frame handles FFmpeg subprocess errors"""
    video_path = "/path/to/video.mp4"
    
    error = subprocess.CalledProcessError(1, 'ffmpeg')
    error.stderr = "FFmpeg error output"
    
    with patch('subprocess.run', side_effect=error), \
         patch('pathlib.Path.is_file', return_value=True), \
         patch('looped_generation.logger') as mock_logger:
        
        with pytest.raises(RuntimeError, match="FFmpeg failed to extract the last frame"):
            extract_last_frame(video_path)
        
        # Check that error was logged
        mock_logger.error.assert_called_once()


def test_extract_last_frame_handles_missing_ffmpeg():
    """Test that extract_last_frame handles missing FFmpeg"""
    video_path = "/path/to/video.mp4"
    
    with patch('subprocess.run', side_effect=FileNotFoundError("ffmpeg not found")), \
         patch('pathlib.Path.is_file', return_value=True), \
         patch('looped_generation.logger'):
        
        with pytest.raises(RuntimeError, match="FFmpeg not found"):
            extract_last_frame(video_path)


def test_extract_last_frame_correct_output_path():
    """Test that extract_last_frame generates correct output path"""
    test_cases = [
        ("/path/to/video.mp4", "/path/to/video_last_frame.png"),
        ("/another/path/movie.mp4", "/another/path/movie_last_frame.png"),
        ("simple_video.mp4", os.path.abspath("simple_video_last_frame.png")),
        ("/complex/path.with.dots/file.mp4", "/complex/path.with.dots/file_last_frame.png"),
    ]
    
    for video_path, expected_png in test_cases:
        with patch('subprocess.run') as mock_subprocess, \
             patch('pathlib.Path.is_file', return_value=True), \
             patch('looped_generation.logger'):
            
            result = extract_last_frame(video_path)
            assert result == expected_png


def test_extract_last_frame_ffmpeg_command_structure():
    """Test that extract_last_frame creates the correct FFmpeg command"""
    video_path = "/test/video.mp4"
    expected_png = "/test/video_last_frame.png"
    
    with patch('subprocess.run') as mock_subprocess, \
         patch('pathlib.Path.is_file', return_value=True), \
         patch('looped_generation.logger'):
        
        extract_last_frame(video_path)
        
        # Check the exact command structure
        call_args = mock_subprocess.call_args[0][0]
        expected_command = [
            "ffmpeg",
            "-sseof",
            "-1",
            "-i",
            video_path,
            "-frames:v",
            "1",
            "-update",
            "1",
            "-f",
            "image2",
            "-y",
            expected_png,
        ]
        
        assert call_args == expected_command


def test_extract_last_frame_with_real_file():
    """Integration test with a real temporary file"""
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_file:
        temp_path = temp_file.name
        temp_file.write(b"dummy video content")
    
    try:
        expected_png = temp_path.replace(".mp4", "_last_frame.png")
        
        # Mock subprocess since we don't have real video content
        with patch('subprocess.run') as mock_subprocess, \
             patch('looped_generation.logger'):
            
            result = extract_last_frame(temp_path)
            
            assert result == expected_png
            mock_subprocess.assert_called_once()
            
    finally:
        # Clean up the temporary file
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def test_extract_last_frame_logging_behavior():
    """Test that extract_last_frame logs appropriately"""
    video_path = "/path/to/video.mp4"
    
    mock_result = MagicMock()
    mock_result.stdout = "FFmpeg debug output"
    
    with patch('subprocess.run', return_value=mock_result), \
         patch('pathlib.Path.is_file', return_value=True), \
         patch('looped_generation.logger') as mock_logger:
        
        extract_last_frame(video_path)
        
        # Check info logging
        mock_logger.info.assert_called_once_with(f"Extracting last frame from: {video_path}")
        
        # Check debug logging
        mock_logger.debug.assert_called_once_with(f"FFmpeg output: {mock_result.stdout}")


def test_extract_last_frame_subprocess_options():
    """Test that extract_last_frame uses correct subprocess options"""
    video_path = "/path/to/video.mp4"
    
    with patch('subprocess.run') as mock_subprocess, \
         patch('pathlib.Path.is_file', return_value=True), \
         patch('looped_generation.logger'):
        
        extract_last_frame(video_path)
        
        # Check that subprocess.run was called with correct options
        call_kwargs = mock_subprocess.call_args[1]
        assert call_kwargs['check'] == True
        assert call_kwargs['capture_output'] == True
        assert call_kwargs['text'] == True