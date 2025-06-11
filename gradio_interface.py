# gradio_interface.py
"""Gradio interface for video generation using the LoopedGeneration class."""
import threading
import queue
import logging
import os

import gradio as gr
from looped_generation import LoopedGeneration

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VideoGenerationInterface:
    """Gradio interface for video generation using LoopedGeneration class."""

    def __init__(self):
        self.generator = LoopedGeneration()
        self.generation_thread = None
        self.is_generating = False
        self.pause_queue = queue.Queue()
        self.pause_event = threading.Event()

    def start_generation(
        self,
        prompt,
        input_image,
        seed_input,
        num_iterations,
        output_dir,
        output_filename,
    ):
        """Start the video generation process"""
        if self.is_generating:
            return "Already generating video. Please wait or pause first."

        self.generator.pause_queue = self.pause_queue
        self.generator.pause_event = self.pause_event

        def run():
            self.is_generating = True
            try:
                self.generator.run_feedback_loop(
                    initial_prompt=prompt,
                    seed=seed_input,
                    input_image_path=input_image,
                    base_output_dir=output_dir,
                    max_iterations=int(num_iterations),
                    stitch_videos=True,
                    stitched_output_filename=output_filename,
                )
            finally:
                self.is_generating = False

        self.generation_thread = threading.Thread(target=run)
        self.generation_thread.start()
        return "Generation started!"

    def pause_generation(self):
        """Pause the generation process"""
        if not self.is_generating:
            return "No generation in progress"
        self.pause_queue.put("PAUSE")
        return "Pausing at next iteration..."

    def resume_generation(self, new_prompt=None, new_image=None):
        """Resume generation with optional new prompt and image"""
        if not self.is_generating:
            return "No generation in progress"

        if new_prompt:
            self.pause_queue.put(f"PROMPT:{new_prompt}")
        if new_image:
            self.pause_queue.put(f"IMAGE:{new_image}")

        self.pause_queue.put("RESUME")
        return "Resuming generation..."


def create_interface():
    """Create the Gradio interface for video generation."""
    interface = VideoGenerationInterface()

    with gr.Blocks() as looper_interface:
        gr.Markdown("# Video Generation Interface")

        with gr.Row():
            with gr.Column():
                prompt_input = gr.Textbox(
                    label="Initial Prompt", placeholder="Enter your prompt here..."
                )
                image_input = gr.Image(label="Input Image (optional)", type="filepath")
                num_iterations = gr.Slider(
                    minimum=1,
                    maximum=200,
                    value=20,
                    step=1,
                    label="Number of Iterations",
                )
                seed_input = gr.Number(
                    label="Random Seed (optional)", value=42, precision=0
                )
                output_dir = gr.Textbox(
                    label="Output Directory", value="outputs/gradio_output"
                )
                output_filename = gr.Textbox(
                    label="Output Filename", value="final_video.mp4"
                )

            with gr.Column():
                status_output = gr.Textbox(label="Status", interactive=False)
                start_btn = gr.Button("Start Generation", variant="primary")
                pause_btn = gr.Button("Pause")

                with gr.Row():
                    new_prompt = gr.Textbox(
                        label="New Prompt (when paused)",
                        placeholder="Enter new prompt to use after pause...",
                    )
                    new_image = gr.Image(
                        label="New Image (when paused)", type="filepath"
                    )
                resume_btn = gr.Button("Resume with New Inputs")

        # Display area for the generated video
        video_path = f"{output_dir}"
        video_output = gr.Video(video_path, label="Generated Video")

        def update_video_output():
            # Function to update the video output display
            video_path = f"{output_dir}/{output_filename}"
            return video_path if os.path.exists(video_path) else None

        # Event handlers
        start_btn.click(
            fn=interface.start_generation,
            inputs=[
                prompt_input,
                image_input,
                seed_input,
                num_iterations,
                output_dir,
                output_filename,
            ],
            outputs=status_output,
        ).then(update_video_output, inputs=[], outputs=[video_output])

        pause_btn.click(fn=interface.pause_generation, inputs=[], outputs=status_output)

        resume_btn.click(
            fn=interface.resume_generation,
            inputs=[new_prompt, new_image],
            outputs=status_output,
        ).then(fn=update_video_output, inputs=[], outputs=[video_output])

    return looper_interface


if __name__ == "__main__":
    looper = create_interface()
    looper.launch(share=False)
