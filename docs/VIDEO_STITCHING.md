# Video Stitching Feature

The video stitching feature allows you to automatically combine all generated video segments from a looped generation run into a single, seamless final video.

## Overview

When running looped video generation, each iteration produces a separate MP4 file. The video stitching feature uses FFmpeg to concatenate these videos into one continuous sequence, creating a longer, flowing video narrative.

## Usage

### Command Line

Enable video stitching by adding the `--stitch-videos` flag:

```bash
python looped_generation.py \
    --prompt "A serene mountain lake at sunset" \
    --iterations 5 \
    --output_dir "outputs/mountain_sequence" \
    --seed 12345 \
    --stitch-videos \
    --stitched-output-filename "mountain_final.mp4"
```

### Programmatic Usage

```python
from looped_generation import LoopedGeneration

# Create instance
looped_gen = LoopedGeneration()

# Run with video stitching enabled
result = looped_gen.run_feedback_loop(
    initial_prompt="A flowing river through a forest",
    seed=9876,
    base_output_dir="outputs/river_sequence",
    max_iterations=4,
    stitch_videos=True,  # Enable stitching
    stitched_output_filename="river_complete.mp4"
)

# result contains path to final stitched video
print(f"Final video saved to: {result}")
```

## Parameters

### `--stitch-videos` / `stitch_videos`
- **Type**: Boolean flag / bool
- **Default**: False
- **Description**: Enable video stitching after all iterations complete

### `--stitched-output-filename` / `stitched_output_filename`
- **Type**: String
- **Default**: "final_stitched_video.mp4"
- **Description**: Filename for the final stitched video

## How It Works

1. **Generate Videos**: The looped generation runs normally, creating individual MP4 files for each iteration
2. **Collect Paths**: After all iterations complete, the system collects paths to all generated MP4 files
3. **Create Concat File**: A temporary text file is created with FFmpeg concat format
4. **Run FFmpeg**: Uses `ffmpeg -f concat` to stitch videos together
5. **Cleanup**: Temporary files are removed
6. **Return Path**: Returns the path to the final stitched video

## Technical Details

### FFmpeg Command
The stitching uses FFmpeg's concat demuxer:

```bash
ffmpeg -f concat -safe 0 -i concat_list.txt -c copy -y output.mp4
```

### Concat File Format
The temporary concat file follows FFmpeg's format:
```
file '/absolute/path/to/video1.mp4'
file '/absolute/path/to/video2.mp4'
file '/absolute/path/to/video3.mp4'
```

### Error Handling
- Validates that video paths exist before stitching
- Handles FFmpeg subprocess errors
- Cleans up temporary files even on failure
- Returns `None` if no videos are found to stitch

## Examples

### Basic Usage
```bash
# Generate 3 iterations and stitch them together
python looped_generation.py \
    --prompt "Waves crashing on a beach" \
    --iterations 3 \
    --stitch-videos
```

### Custom Output Location
```bash
# Specify custom output directory and filename
python looped_generation.py \
    --prompt "City traffic time-lapse" \
    --iterations 6 \
    --output_dir "outputs/city_timelapse" \
    --stitch-videos \
    --stitched-output-filename "traffic_flow_complete.mp4"
```

### Programmatic with Custom Settings
```python
looped_gen = LoopedGeneration()

result = looped_gen.run_feedback_loop(
    initial_prompt="Clouds moving across the sky",
    seed=555,
    base_output_dir="outputs/cloudscape",
    max_iterations=8,
    height=1024,
    width=1920,
    number_of_frames=120,
    stitch_videos=True,
    stitched_output_filename="cloudscape_sequence.mp4"
)
```

## Requirements

- **FFmpeg**: Must be installed and available in PATH
- **Video Files**: At least one MP4 file must be generated during the loop
- **Disk Space**: Ensure sufficient space for the final stitched video

## Troubleshooting

### FFmpeg Not Found
```
RuntimeError: FFmpeg failed to stitch videos: [Errno 2] No such file or directory: 'ffmpeg'
```
**Solution**: Install FFmpeg and ensure it's in your PATH.

### No Videos to Stitch
If no MP4 files are found, the feature will skip stitching and return `None`.

### Disk Space Issues
Ensure you have enough disk space for the final video, which will be roughly the sum of all individual video file sizes.

## Performance Notes

- Video stitching uses FFmpeg's copy codec (`-c copy`) for fast, lossless concatenation
- Processing time depends on the number and size of input videos
- No re-encoding is performed, maintaining original video quality
- Temporary concat file is small (just text) and cleaned up automatically

## Integration with Existing Workflows

The video stitching feature is completely optional and backward-compatible:

- **Default Behavior**: Without the flag, behavior is unchanged
- **Return Values**: Methods return `None` when stitching is disabled, or the path when enabled
- **File Structure**: Individual iteration videos are preserved alongside the stitched result

## Testing

The feature includes comprehensive tests covering:
- Unit tests for the stitching function
- Component tests for integration with LoopedGeneration
- Integration tests for end-to-end workflows
- Error handling and edge cases
- Command line interface testing

Run tests with:
```bash
pytest tests/test_looped_generation/ -v
```
