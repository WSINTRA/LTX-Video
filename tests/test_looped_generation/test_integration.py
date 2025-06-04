import os
import sys
import pytest
from unittest.mock import MagicMock, patch
import tempfile

# Add the parent directory to sys.path to import looped_generation directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from looped_generation import LoopedGeneration, main


def test_integration_video_stitching_end_to_end():
    """
    Integration test demonstrating the complete video stitching workflow.
    
    This test simulates a complete run of the looped generation with video stitching,
    showing how all components work together.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        base_output_dir = os.path.join(temp_dir, "looped_video_test")
        
        # Mock file system to simulate generated videos
        def mock_listdir(path):
            if "frame_000" in path:
                return ["generated_video_0.mp4"]
            elif "frame_001" in path:
                return ["generated_video_1.mp4"]
            else:
                return []
        
        # Mock extract_last_frame to return predictable PNG paths
        def mock_extract_last_frame(video_path):
            return video_path.replace(".mp4", "_last_frame.png")
        
        # Mock subprocess calls (inference and FFmpeg)
        subprocess_calls = []
        def mock_subprocess(cmd):
            subprocess_calls.append(cmd.copy())
        
        # Mock stitch_videos to capture the call and return a path
        stitch_calls = []
        def mock_stitch_videos(video_paths, output_dir, filename="final_stitched_video.mp4"):
            stitch_calls.append({
                'video_paths': video_paths.copy(),
                'output_dir': output_dir,
                'filename': filename
            })
            return os.path.join(output_dir, filename)
        
        # Create the LoopedGeneration instance with all mocks
        looped_gen = LoopedGeneration(
            extract_last_frame_fn=mock_extract_last_frame,
            run_subprocess_fn=mock_subprocess,
            sleep_fn=lambda x: None,  # No sleep for tests
            listdir_fn=mock_listdir,
            makedirs_fn=lambda path, exist_ok=True: None,
            stitch_videos_fn=mock_stitch_videos,
        )
        
        # Run the complete workflow with video stitching enabled
        result = looped_gen.run_feedback_loop(
            initial_prompt="A beautiful landscape with flowing water",
            seed=42,
            base_output_dir=base_output_dir,
            max_iterations=2,
            height=256,
            width=256,
            number_of_frames=10,
            stitch_videos=True,
            stitched_output_filename="landscape_sequence.mp4",
        )
        
        # Verify that the expected number of subprocess calls were made
        assert len(subprocess_calls) == 2  # One initial + one feedback iteration
        
        # Verify the first call (initial generation)
        first_call = subprocess_calls[0]
        assert "--prompt" in first_call
        assert "A beautiful landscape with flowing water" in first_call
        assert "--seed" in first_call
        assert "42" in first_call
        assert "--conditioning_media_paths" not in first_call  # No conditioning for first
        
        # Verify the second call (feedback iteration)
        second_call = subprocess_calls[1]
        assert "--conditioning_media_paths" in second_call
        assert "--seed" in second_call
        assert "43" in second_call  # Incremented seed
        
        # Verify that video stitching was called
        assert len(stitch_calls) == 1
        stitch_call = stitch_calls[0]
        
        # Verify correct video paths were collected
        assert len(stitch_call['video_paths']) == 2
        assert any("frame_000" in path for path in stitch_call['video_paths'])
        assert any("frame_001" in path for path in stitch_call['video_paths'])
        
        # Verify correct output directory and filename
        assert stitch_call['output_dir'] == base_output_dir
        assert stitch_call['filename'] == "landscape_sequence.mp4"
        
        # Verify the return value
        expected_output = os.path.join(base_output_dir, "landscape_sequence.mp4")
        assert result == expected_output


def test_integration_without_video_stitching():
    """
    Integration test for the standard workflow without video stitching.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        base_output_dir = os.path.join(temp_dir, "looped_video_no_stitch")
        
        def mock_listdir(path):
            return ["video.mp4"]  # Always return a video file
        
        subprocess_calls = []
        def mock_subprocess(cmd):
            subprocess_calls.append(cmd.copy())
        
        stitch_calls = []
        def mock_stitch_videos(*args, **kwargs):
            stitch_calls.append(args)
            return "should_not_be_called.mp4"
        
        looped_gen = LoopedGeneration(
            extract_last_frame_fn=lambda x: x.replace(".mp4", "_frame.png"),
            run_subprocess_fn=mock_subprocess,
            sleep_fn=lambda x: None,
            listdir_fn=mock_listdir,
            makedirs_fn=lambda path, exist_ok=True: None,
            stitch_videos_fn=mock_stitch_videos,
        )
        
        # Run without video stitching
        result = looped_gen.run_feedback_loop(
            initial_prompt="Test prompt",
            seed=100,
            base_output_dir=base_output_dir,
            max_iterations=3,
            stitch_videos=False,  # Explicitly disabled
        )
        
        # Verify subprocess calls were made
        assert len(subprocess_calls) == 3  # One initial + two feedback iterations
        
        # Verify video stitching was NOT called
        assert len(stitch_calls) == 0
        
        # Verify no return value when stitching is disabled
        assert result is None


@patch('sys.argv', ['looped_generation.py', '--prompt', 'Test', '--stitch-videos'])
def test_integration_command_line_interface():
    """
    Integration test for the command line interface with video stitching.
    """
    with patch('looped_generation.LoopedGeneration') as MockLoopedGeneration:
        # Mock the LoopedGeneration instance and its methods
        mock_instance = MagicMock()
        mock_instance.run_feedback_loop.return_value = "final_output.mp4"
        MockLoopedGeneration.return_value = mock_instance
        
        # Call the main function
        main()
        
        # Verify that LoopedGeneration was instantiated
        MockLoopedGeneration.assert_called_once()
        
        # Verify that run_feedback_loop was called with correct arguments
        mock_instance.run_feedback_loop.assert_called_once()
        call_kwargs = mock_instance.run_feedback_loop.call_args.kwargs
        
        assert call_kwargs['initial_prompt'] == 'Test'
        assert call_kwargs['stitch_videos'] == True
        assert 'stitched_output_filename' in call_kwargs


def test_integration_error_handling():
    """
    Integration test for error handling in the video stitching workflow.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        base_output_dir = os.path.join(temp_dir, "error_test")
        
        # Mock to simulate FFmpeg error
        def mock_stitch_videos_error(*args, **kwargs):
            raise RuntimeError("FFmpeg failed to stitch videos: Command failed")
        
        looped_gen = LoopedGeneration(
            extract_last_frame_fn=lambda x: x.replace(".mp4", "_frame.png"),
            run_subprocess_fn=lambda x: None,
            sleep_fn=lambda x: None,
            listdir_fn=lambda x: ["video.mp4"],
            makedirs_fn=lambda path, exist_ok=True: None,
            stitch_videos_fn=mock_stitch_videos_error,
        )
        
        # Verify that FFmpeg errors are properly propagated
        with pytest.raises(RuntimeError, match="FFmpeg failed to stitch videos"):
            looped_gen.run_feedback_loop(
                initial_prompt="Test",
                seed=1,
                base_output_dir=base_output_dir,
                max_iterations=1,
                stitch_videos=True,
            )


class TestVideoStitchingDocumentation:
    """
    Documentation tests that serve as usage examples for the video stitching feature.
    
    These tests demonstrate how to use the new video stitching functionality
    and serve as living documentation for the feature.
    """
    
    def test_usage_example_basic_stitching(self):
        """
        Example: Basic usage of video stitching feature.
        
        This example shows how to enable video stitching in a looped generation run.
        """
        # Create a LoopedGeneration instance
        looped_gen = LoopedGeneration()
        
        # Run with video stitching enabled
        # result = looped_gen.run_feedback_loop(
        #     initial_prompt="A serene mountain lake at sunset",
        #     seed=12345,
        #     base_output_dir="outputs/mountain_lake_sequence",
        #     max_iterations=5,
        #     stitch_videos=True,  # Enable video stitching
        #     stitched_output_filename="mountain_lake_final.mp4"
        # )
        # 
        # # result will contain the path to the final stitched video:
        # # "outputs/mountain_lake_sequence/mountain_lake_final.mp4"
        
        # This is a documentation test, so we just verify the interface exists
        assert hasattr(looped_gen, 'run_feedback_loop')
        assert 'stitch_videos' in looped_gen.run_feedback_loop.__code__.co_varnames
        assert 'stitched_output_filename' in looped_gen.run_feedback_loop.__code__.co_varnames
    
    def test_usage_example_command_line(self):
        """
        Example: Command line usage with video stitching.
        
        Command line usage:
        ```bash
        python looped_generation.py \
            --prompt "A flowing river through a forest" \
            --iterations 4 \
            --output_dir "outputs/river_sequence" \
            --seed 9876 \
            --stitch-videos \
            --stitched-output-filename "river_final.mp4"
        ```
        
        This will generate 4 video iterations and then stitch them together
        into a single "river_final.mp4" file.
        """
        # Verify command line arguments are properly defined
        from looped_generation import main
        import argparse
        
        # This test verifies the CLI interface exists
        assert callable(main)
    
    def test_usage_example_without_stitching(self):
        """
        Example: Running without video stitching (default behavior).
        
        If you don't want video stitching, simply omit the stitch_videos parameter
        or set it to False:
        """
        # Create a LoopedGeneration instance
        looped_gen = LoopedGeneration()
        
        # Run without video stitching (default behavior)
        # result = looped_gen.run_feedback_loop(
        #     initial_prompt="A bustling city street",
        #     seed=555,
        #     base_output_dir="outputs/city_sequence",
        #     max_iterations=3,
        #     stitch_videos=False  # Explicitly disabled (or omit this line)
        # )
        # 
        # # result will be None when stitching is disabled
        # assert result is None
        
        # Verify the default behavior
        import inspect
        sig = inspect.signature(looped_gen.run_feedback_loop)
        assert sig.parameters['stitch_videos'].default == False