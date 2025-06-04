import os
import pytest
import tempfile
from unittest.mock import MagicMock, patch, mock_open
import sys

# Add the parent directory to sys.path to import looped_generation directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from looped_generation import stitch_videos


def test_stitch_videos_creates_concat_file_and_calls_ffmpeg():
    """Test that stitch_videos creates the correct concat file and calls FFmpeg"""
    video_paths = ["/path/to/video1.mp4", "/path/to/video2.mp4"]
    output_dir = "/output/dir"
    output_filename = "final.mp4"
    
    with patch('subprocess.run') as mock_subprocess, \
         patch('builtins.open', mock_open()) as mock_file, \
         patch('os.path.exists', return_value=True), \
         patch('os.remove') as mock_remove:
        
        result = stitch_videos(video_paths, output_dir, output_filename)
        
        # Check that the concat file was written correctly
        mock_file.assert_called_with('/output/dir/concat_list.txt', 'w')
        handle = mock_file()
        
        # Check that file.write was called with correct content
        expected_writes = [
            "file '/path/to/video1.mp4'\n",
            "file '/path/to/video2.mp4'\n"
        ]
        actual_writes = [call.args[0] for call in handle.write.call_args_list]
        assert actual_writes == expected_writes
        
        # Check that FFmpeg was called with correct arguments
        mock_subprocess.assert_called_once()
        call_args = mock_subprocess.call_args[0][0]
        expected_command = [
            "ffmpeg",
            "-f", "concat",
            "-safe", "0",
            "-i", "/output/dir/concat_list.txt",
            "-c", "copy",
            "-y",
            "/output/dir/final.mp4"
        ]
        assert call_args == expected_command
        
        # Check that temporary file was cleaned up
        mock_remove.assert_called_once_with('/output/dir/concat_list.txt')
        
        # Check return value
        assert result == "/output/dir/final.mp4"


def test_stitch_videos_raises_error_on_empty_video_list():
    """Test that stitch_videos raises ValueError when no video paths provided"""
    with pytest.raises(ValueError, match="No video paths provided for stitching"):
        stitch_videos([], "/output/dir")


def test_stitch_videos_handles_ffmpeg_error():
    """Test that stitch_videos handles FFmpeg subprocess errors correctly"""
    import subprocess
    
    video_paths = ["/path/to/video1.mp4"]
    output_dir = "/output/dir"
    
    with patch('subprocess.run', side_effect=subprocess.CalledProcessError(1, 'ffmpeg')), \
         patch('builtins.open', mock_open()), \
         patch('os.path.exists', return_value=True), \
         patch('os.remove') as mock_remove:
        
        with pytest.raises(RuntimeError, match="FFmpeg failed to stitch videos"):
            stitch_videos(video_paths, output_dir)
        
        # Ensure cleanup still happens even on error
        mock_remove.assert_called_once_with('/output/dir/concat_list.txt')


def test_stitch_videos_cleans_up_even_if_concat_file_missing():
    """Test that stitch_videos doesn't fail if concat file doesn't exist during cleanup"""
    video_paths = ["/path/to/video1.mp4"]
    output_dir = "/output/dir"
    
    with patch('subprocess.run') as mock_subprocess, \
         patch('builtins.open', mock_open()), \
         patch('os.path.exists', return_value=False), \
         patch('os.remove') as mock_remove:
        
        stitch_videos(video_paths, output_dir)
        
        # Should not try to remove file if it doesn't exist
        mock_remove.assert_not_called()


def test_stitch_videos_uses_absolute_paths():
    """Test that stitch_videos converts paths to absolute paths in concat file"""
    video_paths = ["video1.mp4", "video2.mp4"]  # Relative paths
    output_dir = "/output/dir"
    
    with patch('subprocess.run') as mock_subprocess, \
         patch('builtins.open', mock_open()) as mock_file, \
         patch('os.path.exists', return_value=True), \
         patch('os.remove'), \
         patch('os.path.abspath', side_effect=lambda x: f"/absolute/{x}"):
        
        stitch_videos(video_paths, output_dir)
        
        # Check that absolute paths were written to concat file
        handle = mock_file()
        expected_writes = [
            "file '/absolute/video1.mp4'\n",
            "file '/absolute/video2.mp4'\n"
        ]
        actual_writes = [call.args[0] for call in handle.write.call_args_list]
        assert actual_writes == expected_writes


def test_stitch_videos_default_filename():
    """Test that stitch_videos uses default filename when not specified"""
    video_paths = ["/path/to/video1.mp4"]
    output_dir = "/output/dir"
    
    with patch('subprocess.run') as mock_subprocess, \
         patch('builtins.open', mock_open()), \
         patch('os.path.exists', return_value=True), \
         patch('os.remove'):
        
        result = stitch_videos(video_paths, output_dir)
        
        # Check that default filename was used
        call_args = mock_subprocess.call_args[0][0]
        output_path = call_args[-1]  # Last argument should be output path
        assert output_path == "/output/dir/final_stitched_video.mp4"
        assert result == "/output/dir/final_stitched_video.mp4"


def test_stitch_videos_single_video():
    """Test that stitch_videos works with a single video file"""
    video_paths = ["/path/to/single_video.mp4"]
    output_dir = "/output/dir"
    
    with patch('subprocess.run') as mock_subprocess, \
         patch('builtins.open', mock_open()) as mock_file, \
         patch('os.path.exists', return_value=True), \
         patch('os.remove'):
        
        result = stitch_videos(video_paths, output_dir)
        
        # Should still work with single video
        handle = mock_file()
        expected_writes = ["file '/path/to/single_video.mp4'\n"]
        actual_writes = [call.args[0] for call in handle.write.call_args_list]
        assert actual_writes == expected_writes
        
        assert result == "/output/dir/final_stitched_video.mp4"


def test_stitch_videos_many_videos():
    """Test that stitch_videos works with many video files"""
    video_paths = [f"/path/to/video{i}.mp4" for i in range(10)]
    output_dir = "/output/dir"
    
    with patch('subprocess.run') as mock_subprocess, \
         patch('builtins.open', mock_open()) as mock_file, \
         patch('os.path.exists', return_value=True), \
         patch('os.remove'):
        
        stitch_videos(video_paths, output_dir)
        
        # Should write all video paths to concat file
        handle = mock_file()
        expected_writes = [f"file '/path/to/video{i}.mp4'\n" for i in range(10)]
        actual_writes = [call.args[0] for call in handle.write.call_args_list]
        assert actual_writes == expected_writes