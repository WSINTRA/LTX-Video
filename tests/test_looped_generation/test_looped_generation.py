import os
import sys
import pytest
from unittest.mock import MagicMock, call

# Add the parent directory to sys.path to import looped_generation directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from looped_generation import LoopedGeneration

@pytest.fixture
def dummy_filesystem(tmp_path):
    """
    Sets up a dummy output directory structure with mp4 files for testing.
    Returns a tuple: (base_output_dir, listdir_fn)
    """
    base_output_dir = tmp_path / "outputs"
    base_output_dir.mkdir()
    # Create frame_000, frame_001, frame_002 directories with dummy mp4s
    for i in range(3):
        frame_dir = base_output_dir / f"frame_{str(i).zfill(3)}"
        frame_dir.mkdir()
        # Only frame_000 and frame_001 will be used as previous outputs
        mp4_path = frame_dir / f"video_{i}.mp4"
        mp4_path.write_bytes(b"dummy video content")
    def listdir_fn(path):
        # Return files in the given directory
        return os.listdir(path)
    return str(base_output_dir), listdir_fn

def test_feedback_loop_runs_expected_iterations(monkeypatch, dummy_filesystem):
    base_output_dir, listdir_fn = dummy_filesystem

    # Mocks
    extract_last_frame_fn = MagicMock(side_effect=lambda mp4: mp4.replace(".mp4", "_last_frame.png"))
    run_subprocess_fn = MagicMock()
    sleep_fn = MagicMock()
    makedirs_fn = MagicMock()

    # Instantiate LoopedGeneration with mocks
    looped = LoopedGeneration(
        extract_last_frame_fn=extract_last_frame_fn,
        run_subprocess_fn=run_subprocess_fn,
        sleep_fn=sleep_fn,
        listdir_fn=listdir_fn,
        makedirs_fn=makedirs_fn,
    )

    # Run with 3 iterations (so 1 initial + 2 feedback)
    looped.run_feedback_loop(
        initial_prompt="A test prompt",
        seed=42,
        base_output_dir=base_output_dir,
        max_iterations=3,
        height=128,
        width=128,
        pipeline_config="dummy_config.yaml",
        number_of_frames=5,
        inference_py="dummy_inference.py",
        delay_between_iterations=0.0,
    )

    # makedirs should be called once for the base output dir
    makedirs_fn.assert_called_once_with(base_output_dir, exist_ok=True)

    # The first subprocess call should not use conditioning_media_paths
    first_call = run_subprocess_fn.call_args_list[0][0][0]
    assert "--prompt" in first_call
    assert "--conditioning_media_paths" not in first_call

    # The next two subprocess calls should use conditioning_media_paths and incremented seeds
    for i in range(1, 3):
        call_args = run_subprocess_fn.call_args_list[i][0][0]
        assert "--conditioning_media_paths" in call_args
        assert "--conditioning_start_frames" in call_args
        # The seed should be incremented
        seed_index = call_args.index("--seed")
        assert call_args[seed_index + 1] == str(42 + i)

    # extract_last_frame should be called for each feedback iteration
    assert extract_last_frame_fn.call_count == 2

    # sleep_fn should be called for each feedback iteration
    assert sleep_fn.call_count == 2

def test_feedback_loop_raises_if_no_mp4(monkeypatch, tmp_path):
    base_output_dir = tmp_path / "outputs"
    base_output_dir.mkdir()
    # Create frame_000 with mp4, frame_001 without mp4
    frame_000 = base_output_dir / "frame_000"
    frame_000.mkdir()
    (frame_000 / "video_0.mp4").write_bytes(b"dummy")
    frame_001 = base_output_dir / "frame_001"
    frame_001.mkdir()
    # No mp4 in frame_001

    def listdir_fn(path):
        return os.listdir(path)

    looped = LoopedGeneration(
        extract_last_frame_fn=MagicMock(return_value="dummy_frame.png"),
        run_subprocess_fn=MagicMock(),
        sleep_fn=MagicMock(),
        listdir_fn=listdir_fn,
        makedirs_fn=MagicMock(),
    )

    # Should succeed for first feedback, but fail on second (no mp4 in frame_001)
    with pytest.raises(FileNotFoundError):
        looped.run_feedback_loop(
            initial_prompt="Prompt",
            seed=1,
            base_output_dir=str(base_output_dir),
            max_iterations=3,
            height=64,
            width=64,
            pipeline_config="dummy.yaml",
            number_of_frames=2,
            inference_py="dummy_inference.py",
            delay_between_iterations=0.0,
        )

def test_feedback_loop_calls_all_dependencies(monkeypatch, dummy_filesystem):
    base_output_dir, listdir_fn = dummy_filesystem

    extract_last_frame_fn = MagicMock(side_effect=lambda mp4: mp4.replace(".mp4", "_last_frame.png"))
    run_subprocess_fn = MagicMock()
    sleep_fn = MagicMock()
    makedirs_fn = MagicMock()

    looped = LoopedGeneration(
        extract_last_frame_fn=extract_last_frame_fn,
        run_subprocess_fn=run_subprocess_fn,
        sleep_fn=sleep_fn,
        listdir_fn=listdir_fn,
        makedirs_fn=makedirs_fn,
    )

    looped.run_feedback_loop(
        initial_prompt="Prompt",
        seed=0,
        base_output_dir=base_output_dir,
        max_iterations=2,
        height=32,
        width=32,
        pipeline_config="dummy.yaml",
        number_of_frames=1,
        inference_py="dummy_inference.py",
        delay_between_iterations=0.0,
    )

    # All dependencies should be called at least once
    assert makedirs_fn.called
    assert run_subprocess_fn.called
    assert extract_last_frame_fn.called
    assert sleep_fn.called