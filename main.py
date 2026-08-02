# main.py

import os
import tempfile
from fastapi import FastAPI, UploadFile, File, HTTPException
from services.whisper_service import transcribe_audio_file

app = FastAPI(title="Neuroclear API")


# --- Your original main() converted into a root endpoint ---
@app.get("/")
def read_root():
    """Health check endpoint to verify the API is running."""
    return {"message": "Hello from neuroclear!"}


# -----------------------------------------------------------


@app.post("/transcribe")
async def transcribe_endpoint(file: UploadFile = File(...)):
    # 1. Validate the file type
    if not file.filename.endswith((".wav", ".mp3", ".m4a", ".flac")):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Please upload a valid audio file.",
        )

    # 2. Save the uploaded file to a temporary location
    file_extension = os.path.splitext(file.filename)[1]

    with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_audio:
        temp_audio.write(await file.read())
        temp_file_path = temp_audio.name

    try:
        # 3. Pass the file path to our isolated business logic
        result = transcribe_audio_file(temp_file_path)
        return result

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

    finally:
        # 4. Clean up: Delete the temporary file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
