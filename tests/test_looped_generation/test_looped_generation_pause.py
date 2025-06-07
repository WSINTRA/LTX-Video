# tests/test_looped_generation/test_looped_generation_pause.py
import logging
import pytest
from unittest.mock import Mock
import threading
import queue
import time

# Set up logging for the test
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(threadName)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class MockSubprocess:
    def __init__(self):
        self.calls = []

    def __call__(self, cmd):
        logger.debug(f"Mock subprocess called with: {cmd}")
        self.calls.append(cmd)
        time.sleep(0.1)  # Simulate some work
        return Mock()  # Return a mock object to simulate subprocess.run result


def verify_thread_running(thread, timeout=1.0):
    """Helper function to verify thread is running"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if thread.is_alive():
            return True
        time.sleep(0.1)
    return False


def test_pause_between_iterations():
    """Test that the generation loop can be paused between iterations"""
    logger.info("Starting test")

    # Mock dependencies
    mock_extract_frame = Mock(return_value="test_frame.png")
    mock_subprocess = MockSubprocess()
    mock_sleep = Mock()
    mock_listdir = Mock(return_value=["output.mp4"])
    mock_makedirs = Mock()
    mock_stitch = Mock()

    # Create a queue for pause signals
    pause_queue = queue.Queue()
    pause_event = threading.Event()

    from looped_generation import LoopedGeneration

    generator = LoopedGeneration(
        extract_last_frame_fn=mock_extract_frame,
        run_subprocess_fn=mock_subprocess,
        sleep_fn=mock_sleep,
        listdir_fn=mock_listdir,
        makedirs_fn=mock_makedirs,
        stitch_videos_fn=mock_stitch,
    )

    # Set up pause control
    generator.pause_queue = pause_queue
    generator.pause_event = pause_event

    generation_thread = None
    try:

        def run_generation():
            try:
                logger.info("Generation thread starting feedback loop")
                generator.run_feedback_loop(
                    initial_prompt="test prompt",
                    seed=42,
                    max_iterations=3,
                    base_output_dir="test_output",
                )
                logger.info("Generation thread completed feedback loop")
            except Exception as e:
                logger.error(f"Error in generation thread: {e}", exc_info=True)
                raise

        generation_thread = threading.Thread(
            target=run_generation, name="GenerationThread"
        )
        logger.info("Starting generation thread")
        generation_thread.start()

        # Verify thread is running
        assert verify_thread_running(
            generation_thread
        ), "Generation thread failed to start"
        logger.info("Generation thread is running")

        # Wait for first subprocess call
        timeout = 1.0
        start_time = time.time()
        while not mock_subprocess.calls and (time.time() - start_time < timeout):
            time.sleep(0.1)

        assert mock_subprocess.calls, "No subprocess calls made"
        logger.info("First subprocess call confirmed")

        # Send pause signal
        logger.info("Sending PAUSE signal")
        pause_queue.put("PAUSE")

        # Wait for pause to take effect
        timeout = 2.0
        start_time = time.time()
        while not pause_event.is_set() and (time.time() - start_time < timeout):
            logger.debug("Waiting for pause to take effect...")
            time.sleep(0.1)

        assert pause_event.is_set(), "Generation should be paused"
        logger.info("Pause confirmed")

        # Test changing prompt and image during pause
        logger.info("Sending new prompt and image")
        pause_queue.put("PROMPT:new test prompt")
        pause_queue.put("IMAGE:new_test_image.png")
        time.sleep(0.1)

        # Resume generation
        logger.info("Sending RESUME signal")
        pause_queue.put("RESUME")

        # Wait for completion
        logger.info("Waiting for generation thread to complete")
        generation_thread.join(timeout=2)

        # Verify the subprocess calls
        assert len(mock_subprocess.calls) > 0, "Should have run at least one iteration"
        logger.info(f"Total subprocess calls: {len(mock_subprocess.calls)}")

        # Verify the new prompt and image were used
        assert any(
            "new test prompt" in str(call) for call in mock_subprocess.calls
        ), "New prompt should be used"
        assert any(
            "new_test_image.png" in str(call) for call in mock_subprocess.calls
        ), "New image should be used"

    finally:
        # Cleanup
        logger.info("Starting cleanup")
        if generation_thread and generation_thread.is_alive():
            logger.info("Thread still alive, sending RESUME and waiting for completion")
            pause_queue.put("RESUME")
            generation_thread.join(timeout=1)
        logger.info("Test cleanup complete")


if __name__ == "__main__":
    pytest.main([__file__])
