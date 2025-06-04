import subprocess
import os
import time
from pathlib import Path
import argparse


def extract_last_frame(video_path: str) -> str:
    """
    Extracts the last frame of the video as a PNG file.

    Args:
        video_path (str): The path to the input video file (e.g., .mp4).

    Returns:
        str: The path to the extracted PNG file.
    """
    # Ensure the video file exists
    video_file = Path(video_path)
    if not video_file.is_file():
        raise FileNotFoundError(f"The video file '{video_path}' does not exist.")

    # Create PNG filename based on video path
    png_path = video_file.with_name(video_file.stem + "_last_frame.png")

    # FFmpeg command to extract the last frame
    command = [
        "ffmpeg",
        "-sseof",
        "-1",  # Seek to 1 second before the end of the file
        "-i",
        str(video_path),
        "-frames:v",
        "1",  # Extract only one frame
        "-update",
        "1",  # Ensure a single image is written
        "-f",
        "image2",
        "-y",
        str(png_path),
    ]

    try:
        # Run the FFmpeg command
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"FFmpeg failed to extract the last frame: {e}")

    return str(png_path)


def run_feedback_loop(
    initial_prompt,
    base_output_dir="outputs/looped_video_005",
    max_iterations=10,
    height=512,
    width=768,
    seed=110101011,
    pipeline_config="configs/ltxv-13b-0.9.7-distilled.yaml",
):
    # Create output directory if it doesn't exist
    os.makedirs(base_output_dir, exist_ok=True)

    # Configs
    number_of_frames = 60

    # First iteration with text prompt
    first_output = f"{base_output_dir}/frame_000"

    # Initial command with text prompt
    first_cmd = [
        "python",
        "inference.py",
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

    # Run first inference
    print(f"Running first iteration: {' '.join(first_cmd)}")
    subprocess.run(first_cmd, check=True)

    # Subsequent iterations using previous output's last frame as input
    for i in range(1, max_iterations):
        prev_output = f"{base_output_dir}/frame_{str(i-1).zfill(3)}"
        current_output = f"{base_output_dir}/frame_{str(i).zfill(3)}"

        files = os.listdir(prev_output)
        mp4_files = [f for f in files if f.endswith(".mp4")]
        if not mp4_files:
            raise FileNotFoundError(f"No .mp4 file found in {prev_output}")

        input_mp4 = os.path.join(prev_output, mp4_files[0])
        last_frame_png = extract_last_frame(input_mp4)

        cmd = [
            "python",
            "inference.py",
            "--prompt",
            initial_prompt,
            "--conditioning_media_paths",
            last_frame_png,  # Use PNG instead of video
            "--conditioning_start_frames",
            "0",
            "--height",
            str(height),
            "--width",
            str(width),
            "--seed",
            str(seed + i),  # Increment seed for variety
            "--num_frames",
            str(number_of_frames),
            "--pipeline_config",
            pipeline_config,
            "--output_path",
            current_output,
        ]

        print(f"Running iteration {i}: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)
        print(f"Completed iteration {i}")

        # Optional: Clean up the PNG file
        # os.remove(last_frame_png)

        # Optional: Add delay between iterations
        time.sleep(1)


if __name__ == "__main__":
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

    # Parse arguments
    args = parser.parse_args()

    # Example usage with command-line arguments
    run_feedback_loop(
        initial_prompt=args.prompt,
        base_output_dir=args.output_dir,
        max_iterations=args.iterations,
    )  # Example usage
