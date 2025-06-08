import subprocess
import os
import time
import threading
import queue
import logging
from pathlib import Path
import argparse
from typing import Callable, Optional, List, Union

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Constants
DEFAULT_OUTPUT_DIR = "outputs/looped_video"
DEFAULT_PIPELINE_CONFIG = "configs/ltxv-13b-0.9.7-distilled.yaml"
DEFAULT_STITCHED_FILENAME = "final_stitched_video.mp4"
CONCAT_TEMP_FILENAME = "concat_list.txt"


def extract_last_frame(video_path: str) -> str:
    """
    Extracts the last frame of the video as a PNG file.

    Args:
        video_path (str): The path to the input video file (e.g., .mp4).

    Returns:
        str: The path to the extracted PNG file.

    Raises:
        FileNotFoundError: If the video file does not exist.
        RuntimeError: If FFmpeg fails to extract the frame.
        ValueError: If the video_path is empty or invalid.
    """
    if not video_path or not video_path.strip():
        raise ValueError("Video path cannot be empty")

    # Validate and sanitize the path
    video_path = os.path.abspath(video_path.strip())
    video_file = Path(video_path)
    if not video_file.is_file():
        raise FileNotFoundError(f"The video file '{video_path}' does not exist.")

    png_path = video_file.with_name(video_file.stem + "_last_frame.png")

    command = [
        "ffmpeg",
        "-sseof",
        "-1",
        "-i",
        str(video_path),
        "-frames:v",
        "1",
        "-update",
        "1",
        "-f",
        "image2",
        "-y",
        str(png_path),
    ]

    try:
        logger.info(f"Extracting last frame from: {video_path}")
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        logger.debug(f"FFmpeg output: {result.stdout}")
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg failed to extract last frame: {e.stderr}")
        raise RuntimeError(f"FFmpeg failed to extract the last frame: {e}")
    except FileNotFoundError:
        raise RuntimeError(
            "FFmpeg not found. Please ensure FFmpeg is installed and in PATH."
        )

    return str(png_path)


def stitch_videos(
    video_paths: List[str],
    output_dir: str,
    output_filename: str = DEFAULT_STITCHED_FILENAME,
) -> str:
    """
    Stitches multiple MP4 videos together into one final output using FFmpeg.

    Args:
        video_paths (List[str]): List of paths to MP4 files to stitch together
        output_dir (str): Directory where the final output should be saved
        output_filename (str): Name of the final output file

    Returns:
        str: Path to the final stitched video file

    Raises:
        ValueError: If no video paths provided or invalid parameters.
        FileNotFoundError: If any video file does not exist.
        RuntimeError: If FFmpeg fails to stitch videos.
    """
    if not video_paths:
        raise ValueError("No video paths provided for stitching")

    if not output_dir or not output_dir.strip():
        raise ValueError("Output directory cannot be empty")

    if not output_filename or not output_filename.strip():
        raise ValueError("Output filename cannot be empty")

    # Validate that all video files exist
    missing_files = []
    for video_path in video_paths:
        if not os.path.isfile(video_path):
            missing_files.append(video_path)

    if missing_files:
        raise FileNotFoundError(f"Video files not found: {missing_files}")

    # Sanitize paths
    output_dir = os.path.abspath(output_dir.strip())
    output_filename = output_filename.strip()
    output_path = os.path.join(output_dir, output_filename)

    # Create a temporary file list for FFmpeg concat
    concat_file_path = os.path.join(output_dir, CONCAT_TEMP_FILENAME)

    try:
        # Write the concat file with proper FFmpeg format
        with open(concat_file_path, "w") as f:
            for video_path in video_paths:
                # FFmpeg concat format: file 'path/to/video.mp4'
                f.write(f"file '{os.path.abspath(video_path)}'\n")

        # FFmpeg command to concatenate videos
        command = [
            "ffmpeg",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            concat_file_path,
            "-c",
            "copy",
            "-y",  # Overwrite output file if it exists
            output_path,
        ]
        logger.debug(f"FFmpeg command: {' '.join(command)}")
        logger.info(f"Stitching {len(video_paths)} videos into: {output_path}")
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        logger.debug(f"FFmpeg concat output: {result.stdout}")
        logger.info(f"Successfully created stitched video: {output_path}")

    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg failed to stitch videos: {e.stderr}")
        raise RuntimeError(f"FFmpeg failed to stitch videos: {e}")
    except FileNotFoundError:
        raise RuntimeError(
            "FFmpeg not found. Please ensure FFmpeg is installed and in PATH."
        )
    finally:
        # Clean up the temporary concat file
        if os.path.exists(concat_file_path):
            try:
                os.remove(concat_file_path)
                logger.debug(f"Cleaned up temporary file: {concat_file_path}")
            except OSError as e:
                logger.warning(
                    f"Failed to remove temporary file {concat_file_path}: {e}"
                )

    return output_path


class LoopedGeneration:
    """
    A class for running looped video generation with optional video stitching.

    This class manages the iterative generation of videos where each iteration
    uses the last frame of the previous video as conditioning input. Optionally,
    all generated videos can be stitched together into a final output.

    Attributes:
        extract_last_frame_fn: Function to extract the last frame from a video
        run_subprocess_fn: Function to run subprocess commands
        sleep_fn: Function to sleep between iterations
        listdir_fn: Function to list directory contents
        makedirs_fn: Function to create directories
        stitch_videos_fn: Function to stitch videos together
    """

    def __init__(
        self,
        extract_last_frame_fn: Callable[[str], str] = extract_last_frame,
        run_subprocess_fn: Optional[Callable[[List[str]], None]] = None,
        sleep_fn: Optional[Callable[[float], None]] = None,
        listdir_fn: Optional[Callable[[str], List[str]]] = None,
        makedirs_fn: Optional[Callable[[str], bool]] = None,
        stitch_videos_fn: Optional[Callable[[List[str], str, str], str]] = None,
    ):
        """
        Initialize the LoopedGeneration instance.

        Args:
            extract_last_frame_fn: Function to extract last frame from video
            run_subprocess_fn: Function to run subprocess commands
            sleep_fn: Function to sleep between iterations
            listdir_fn: Function to list directory contents
            makedirs_fn: Function to create directories
            stitch_videos_fn: Function to stitch videos together
        """
        self.extract_last_frame_fn = extract_last_frame_fn
        self.run_subprocess_fn = run_subprocess_fn or self._default_run_subprocess
        self.sleep_fn = sleep_fn or time.sleep
        self.listdir_fn = listdir_fn or os.listdir
        self.makedirs_fn = makedirs_fn or self._default_makedirs
        self.stitch_videos_fn = stitch_videos_fn or stitch_videos
        self.pause_queue = queue.Queue()
        self.pause_event = threading.Event()
        self.current_prompt = None
        self.current_image = None

    def check_pause_status(self):
        """Check if a pause has been requested and handle it"""
        try:
            while True:
                signal: str = self.pause_queue.get_nowait()
                logger.info(f"Received signal: {signal}")  # Add logging
                if signal == "PAUSE":
                    logger.info("Pausing generation...")
                    self.pause_event.set()

                elif signal == "RESUME":
                    logger.info("Resuming generation...")
                    self.pause_event.clear()
                elif signal.startswith("PROMPT:"):
                    logger.info(f"Updating prompt: {signal[7:]}")
                    self.current_prompt = signal[7:]
                elif signal.startswith("IMAGE:"):
                    logger.info(f"Updating conditioning image: {signal[6:]}")
                    self.current_image = signal[6:]
        except queue.Empty:
            pass

        if self.pause_event.is_set():
            logger.info("Generation paused. Waiting for resume signal...")
            while self.pause_event.is_set():
                try:
                    # Continue processing commands while paused
                    signal = self.pause_queue.get(timeout=0.1)
                    if signal == "RESUME":
                        logger.info("Received resume signal")
                        self.pause_event.clear()
                    elif signal.startswith("PROMPT:"):
                        self.current_prompt = signal[7:]
                        logger.info(f"Updated prompt to: {self.current_prompt}")
                    elif signal.startswith("IMAGE:"):
                        self.current_image = signal[6:]
                        logger.info(f"Updated image to: {self.current_image}")
                except queue.Empty:
                    continue

    @staticmethod
    def _default_run_subprocess(cmd: List[str]) -> None:
        """Default subprocess runner with security validation."""
        # Basic security check - ensure we're only running python and known commands
        allowed_commands = ["python", "python3"]
        if cmd and cmd[0] not in allowed_commands:
            raise ValueError(f"Command not allowed: {cmd[0]}")
        subprocess.run(cmd, check=True)

    @staticmethod
    def _default_makedirs(path: str, exist_ok: bool = True) -> None:
        """Default directory creation function."""
        os.makedirs(path, exist_ok=exist_ok)

    def _find_mp4_files(self, directory: str) -> List[str]:
        """
        Find MP4 files in a directory.

        Args:
            directory: Directory to search in

        Returns:
            List of MP4 filenames found in the directory
        """
        try:
            files = self.listdir_fn(directory)
            return [f for f in files if f.endswith(".mp4")]
        except OSError as e:
            logger.error(f"Failed to list directory {directory}: {e}")
            return []

    def run_feedback_loop(
        self,
        initial_prompt: str,
        seed: int,
        input_image_path: Optional[str] = None,
        base_output_dir: str = DEFAULT_OUTPUT_DIR,
        max_iterations: int = 10,
        height: int = 512,
        width: int = 768,
        pipeline_config: str = DEFAULT_PIPELINE_CONFIG,
        number_of_frames: int = 96,
        inference_py: str = "inference.py",
        delay_between_iterations: float = 1.0,
        stitch_videos: bool = False,
        stitched_output_filename: str = DEFAULT_STITCHED_FILENAME,
    ) -> Optional[str]:
        """
        Run the feedback loop for iterative video generation.

        Args:
            initial_prompt: Text prompt for video generation
            seed: Random seed for reproducibility
            base_output_dir: Base directory for outputs
            max_iterations: Number of iterations to run
            height: Video height in pixels
            width: Video width in pixels
            pipeline_config: Path to pipeline configuration file
            number_of_frames: Number of frames per video
            inference_py: Path to inference script
            delay_between_iterations: Delay between iterations in seconds
            stitch_videos: Whether to stitch videos together at the end
            stitched_output_filename: Filename for stitched output

        Returns:
            Path to stitched video if stitch_videos=True, otherwise None

        Raises:
            ValueError: If parameters are invalid
            FileNotFoundError: If required files are missing
            RuntimeError: If subprocess commands fail
        """
        logger.info("Starting feedback loop")
        self.current_prompt = initial_prompt
        self.check_pause_status()
        # Input validation
        if not initial_prompt or not initial_prompt.strip():
            raise ValueError("Initial prompt cannot be empty")

        if max_iterations < 1:
            raise ValueError("max_iterations must be at least 1")

        if height < 1 or width < 1:
            raise ValueError("Height and width must be positive")

        if number_of_frames < 1:
            raise ValueError("number_of_frames must be positive")

        if delay_between_iterations < 0:
            raise ValueError("delay_between_iterations cannot be negative")

        logger.info(f"Starting feedback loop with {max_iterations} iterations")
        logger.info(f"Prompt: {initial_prompt}")
        logger.info(f"Output directory: {base_output_dir}")
        self.makedirs_fn(base_output_dir, exist_ok=True)

        first_output = f"{base_output_dir}/frame_000"
        first_cmd = [
            "python",
            inference_py,
            "--prompt",
            initial_prompt,
            "--height",
            str(height),
            "--width",
            str(width),
            "--seed",
            str(seed),
            "--num_frames",
            str(number_of_frames),
            "--pipeline_config",
            pipeline_config,
            "--output_path",
            first_output,
        ]
        if input_image_path:
            first_cmd.extend(
                [
                    "--conditioning_media_paths",
                    input_image_path,
                    "--conditioning_start_frames",
                    "0",
                ]
            )

        logger.info(f"Running first iteration: {' '.join(first_cmd)}")
        try:
            self.run_subprocess_fn(first_cmd)
            logger.info("First iteration completed successfully")
        except subprocess.CalledProcessError as e:
            logger.error(f"First iteration failed: {e}")
            raise

        for i in range(1, max_iterations):
            self.check_pause_status()
            prev_output = f"{base_output_dir}/frame_{str(i-1).zfill(3)}"
            current_output = f"{base_output_dir}/frame_{str(i).zfill(3)}"

            mp4_files = self._find_mp4_files(prev_output)
            if not mp4_files:
                raise FileNotFoundError(f"No .mp4 file found in {prev_output}")

            input_mp4 = os.path.join(prev_output, mp4_files[0])
            #last_frame_png = self.extract_last_frame_fn(input_mp4)

            #conditioning_paths = []
            #if self.current_image:  # If user provided a new image during pause
            #    conditioning_paths.append(self.current_image)
            #else:
            #    conditioning_paths.append(last_frame_png)
            cmd = [
                "python",
                inference_py,
                "--prompt",
                self.current_prompt,
                "--conditioning_media_paths",
                input_mp4,  # Use the last video as conditioning input
                "--conditioning_start_frames",
                "0",
                "--height",
                str(height),
                "--width",
                str(width),
                "--seed",
                str(seed + i),
                "--num_frames",
                str(number_of_frames),
                "--pipeline_config",
                pipeline_config,
                "--output_path",
                current_output,
            ]
            logger.info(f"Running iteration {i}: {' '.join(cmd)}")
            try:
                self.run_subprocess_fn(cmd)
                logger.info(f"Completed iteration {i}")
            except subprocess.CalledProcessError as e:
                logger.error(f"Iteration {i} failed: {e}")
                raise

            self.sleep_fn(delay_between_iterations)

        # After all iterations reset the current prompt and image
        self.current_prompt = None
        self.current_image = None
        # After all iterations, stitch videos if requested
        if stitch_videos:
            logger.info("Collecting videos for stitching")
            video_paths = []
            for i in range(max_iterations):
                frame_output = f"{base_output_dir}/frame_{str(i).zfill(3)}"
                mp4_files = self._find_mp4_files(frame_output)
                if mp4_files:
                    video_path = os.path.join(frame_output, mp4_files[0])
                    video_paths.append(video_path)
                    logger.debug(f"Found video for iteration {i}: {video_path}")

            if video_paths:
                logger.info(f"Stitching {len(video_paths)} videos together")
                final_output = self.stitch_videos_fn(
                    video_paths, base_output_dir, stitched_output_filename
                )
                logger.info(f"Video stitching completed: {final_output}")
                return final_output
            else:
                logger.warning("No videos found to stitch")

        logger.info("Feedback loop completed")
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Run feedback loop with text-to-video generation"
    )
    parser.add_argument(
        "--prompt",
        "-p",
        type=str,
        required=True,
        help="Initial text prompt for video generation",
    )
    parser.add_argument(
        "--iterations",
        "-i",
        type=int,
        default=10,
        help="Number of iterations for the feedback loop (default: 10)",
    )
    parser.add_argument(
        "--output_dir",
        "-o",
        type=str,
        default=DEFAULT_OUTPUT_DIR.replace("005", "001"),
        help='Base output directory (default: "outputs/looped_video_001")',
    )
    parser.add_argument(
        "--seed",
        "-s",
        type=int,
        default=1337,
        help="Random seed for reproducibility (default: 1337)",
    )
    parser.add_argument(
        "--stitch-videos",
        action="store_true",
        help="Stitch all generated videos together into one final output",
    )
    parser.add_argument(
        "--stitched-output-filename",
        type=str,
        default=DEFAULT_STITCHED_FILENAME,
        help="Filename for the final stitched video (default: final_stitched_video.mp4)",
    )

    args = parser.parse_args()

    try:
        looped_gen = LoopedGeneration()
        result = looped_gen.run_feedback_loop(
            initial_prompt=args.prompt,
            base_output_dir=args.output_dir,
            max_iterations=args.iterations,
            seed=args.seed,
            stitch_videos=args.stitch_videos,
            stitched_output_filename=args.stitched_output_filename,
        )

        if result:
            print(f"Final stitched video saved to: {result}")
        else:
            print(
                "Video generation completed. Individual videos are in the output directory."
            )

    except Exception as e:
        logger.error(f"Error during execution: {e}")
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
