import subprocess
import os
import time
from pathlib import Path
import argparse
from typing import Callable, Optional, List


def extract_last_frame(video_path: str) -> str:
    """
    Extracts the last frame of the video as a PNG file.

    Args:
        video_path (str): The path to the input video file (e.g., .mp4).

    Returns:
        str: The path to the extracted PNG file.
    """
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
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"FFmpeg failed to extract the last frame: {e}")

    return str(png_path)


class LoopedGeneration:
    def __init__(
        self,
        extract_last_frame_fn: Callable[[str], str] = extract_last_frame,
        run_subprocess_fn: Callable[[List[str]], None] = None,
        sleep_fn: Callable[[float], None] = None,
        listdir_fn: Callable[[str], List[str]] = None,
        makedirs_fn: Callable[[str, bool], None] = None,
    ):
        self.extract_last_frame_fn = extract_last_frame_fn
        self.run_subprocess_fn = run_subprocess_fn or self._default_run_subprocess
        self.sleep_fn = sleep_fn or time.sleep
        self.listdir_fn = listdir_fn or os.listdir
        self.makedirs_fn = makedirs_fn or os.makedirs

    @staticmethod
    def _default_run_subprocess(cmd: List[str]):
        subprocess.run(cmd, check=True)

    def run_feedback_loop(
        self,
        initial_prompt: str,
        seed: int,
        base_output_dir: str = "outputs/looped_video_005",
        max_iterations: int = 10,
        height: int = 512,
        width: int = 768,
        pipeline_config: str = "configs/ltxv-13b-0.9.7-distilled.yaml",
        number_of_frames: int = 60,
        inference_py: str = "inference.py",
        delay_between_iterations: float = 1.0,
    ):
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

        print(f"Running first iteration: {' '.join(first_cmd)}")
        self.run_subprocess_fn(first_cmd)

        for i in range(1, max_iterations):
            prev_output = f"{base_output_dir}/frame_{str(i-1).zfill(3)}"
            current_output = f"{base_output_dir}/frame_{str(i).zfill(3)}"

            files = self.listdir_fn(prev_output)
            mp4_files = [f for f in files if f.endswith(".mp4")]
            if not mp4_files:
                raise FileNotFoundError(f"No .mp4 file found in {prev_output}")

            input_mp4 = os.path.join(prev_output, mp4_files[0])
            last_frame_png = self.extract_last_frame_fn(input_mp4)

            cmd = [
                "python",
                inference_py,
                "--prompt",
                initial_prompt,
                "--conditioning_media_paths",
                last_frame_png,
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

            print(f"Running iteration {i}: {' '.join(cmd)}")
            self.run_subprocess_fn(cmd)
            print(f"Completed iteration {i}")

            self.sleep_fn(delay_between_iterations)


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
        default="outputs/looped_video_001",
        help='Base output directory (default: "outputs/looped_video_001")',
    )
    parser.add_argument(
        "--seed",
        "-s",
        type=int,
        default=1337,
        help="Random seed for reproducibility (default: 1337)",
    )

    args = parser.parse_args()

    looped_gen = LoopedGeneration()
    looped_gen.run_feedback_loop(
        initial_prompt=args.prompt,
        base_output_dir=args.output_dir,
        max_iterations=args.iterations,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
