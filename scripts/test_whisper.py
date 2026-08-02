import os
import time
import torch
from transformers import pipeline

print("Loading the model 'openai/whisper-tiny'...")
# device = "cuda" if torch.cuda.is_available() else "cpu"
device = "cpu"
# The pipeline function simplifies the process of loading the model and processor.
# We specify the task "automatic-speech-recognition" and the model name.
asr_pipeline = pipeline(
    "automatic-speech-recognition", model="openai/whisper-tiny", device=device
)

# Pointing to the specific audio file requested.
audio_file_path = "data/raw/sample.wav"


def transcribe_audio(file_path, pipe):
    """
    Transcribes the given audio file using the provided ASR pipeline.

    Args:
        file_path (str): The path to the audio file (e.g., .wav, .mp3).
        pipe: The initialized transformers pipeline for ASR.
    """
    if not os.path.exists(file_path):
        print(f"Error: The file '{file_path}' was not found.")
        print(
            "Please ensure the 'data/raw' directory exists and contains 'sample.wav'."
        )
        return

    print(f"\nProcessing '{file_path}'...")

    try:
        start_time = time.perf_counter()
        
        result = pipe(file_path)

        end_time = time.perf_counter()
        inference_time = end_time - start_time

        print("\n--- Transcription Result ---")
        # The result is typically a dictionary containing the 'text' key.
        print(result["text"])
        print("----------------------------")
        print(f"Inference time: {inference_time:.3f} seconds")

    except Exception as e:
        print(f"An error occurred during transcription: {e}")


if __name__ == "__main__":
    transcribe_audio(audio_file_path, asr_pipeline)
