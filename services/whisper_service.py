# services/whisper_service.py

import os
import time
import torch
from transformers import pipeline

print("Loading the model 'openai/whisper-tiny'...")
device = "cuda" if torch.cuda.is_available() else "cpu"

# Load the pipeline globally so it only initializes once when the app starts
asr_pipeline = pipeline(
    "automatic-speech-recognition", model="openai/whisper-tiny", device=device
)


def transcribe_audio_file(file_path: str) -> dict:
    """
    Transcribes the given audio file using the global ASR pipeline.

    Args:
        file_path (str): The absolute or relative path to the audio file.

    Returns:
        dict: A dictionary containing the transcription text and inference time.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"The file '{file_path}' was not found.")

    print(f"\nProcessing '{file_path}'...")

    start_time = time.perf_counter()

    # Run the model
    result = asr_pipeline(file_path, chunk_length_s=30, return_timestamps=True)

    end_time = time.perf_counter()
    inference_time = end_time - start_time

    return {"text": result["text"], "inference_time_seconds": round(inference_time, 3)}
