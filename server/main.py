
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
import uvicorn
import os
from glob import glob
import shutil
import json
import numpy as np
import sys
import io
import base64
import cv2
from pathlib import Path

# Get the absolute path to the directory containing the function
function_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'SegInference'))

# Add this directory to Python's search path
sys.path.append(function_dir)
from inference import segmentation_

app = FastAPI()

upload_dir = r"D:\courses-2025\prototype\server\uploads"
if not os.path.exists(upload_dir) :
    os.mkdir(upload_dir)

@app.get('/')
async def root():
    return {'message': 'Backend Initiated...'}

@app.post('/segment')
async def seg(
    media: UploadFile = File(...),
    prompt: str = Form(...),
    coordinates: str = Form(...)
):
    
    #https://fastapi.tiangolo.com/tutorial/header-param-models/#check-the-docs
    #https://fastapi.tiangolo.com/tutorial/request-forms/#import-
    
    # Define the path to save the uploaded file
    media_path = upload_dir + "\\" + media.filename
    # print("media_path", media_path)

    # Save the uploaded file to the local directory
    with open(media_path, "wb") as buffer:
        shutil.copyfileobj(media.file, buffer)

    # Parse the JSON string for coordinates
    parsed_coordinates = json.loads(coordinates)
    #for coord in parsed_coordinates[0]:
    coord_path = media_path.split('.')[0] + '.txt'
    with open(coord_path, "w") as f:
        f.writelines(prompt)
        f.writelines("\n")
        f.writelines("\n")
        f.writelines(str(np.array(parsed_coordinates)))

    print('image', media.filename)
    print('prompt', prompt)
    print('coords', coordinates)
        
    seg_img = segmentation_(media_path, parsed_coordinates)
    is_success, buffer = cv2.imencode(".png", seg_img)
    io_buf = io.BytesIO(buffer)

    #Path(media_path).unlink()
    
    # Return the Base64 encoded string
    seg_img = base64.b64encode(io_buf.getvalue()).decode('utf-8')

    return {
            "message": "Image segmented successfully!",
            "segmented_image": seg_img
        }
    
    


if __name__ == "__main__":
    uvicorn.run(app, host="192.168.1.5", port=3000)





'''

# main.py
import uvicorn
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from pathlib import Path
import json
import shutil

# Initialize the FastAPI application
app = FastAPI()

# Create a directory to store uploaded files
UPLOAD_DIRECTORY = Path("uploads")
UPLOAD_DIRECTORY.mkdir(exist_ok=True)

# Define a root endpoint
@app.get("/")
async def root():
    return {"message": "Backend is running!"}

# Endpoint to handle media uploads and segmentation data
@app.post("/segment")
async def segment_image(
    media: UploadFile = File(...),
    prompt: str = Form(...),
    coordinates: str = Form(...)
):
    try:
        # Check if a file was uploaded
        if not media.filename:
            raise HTTPException(status_code=400, detail="No media file uploaded.")
        
        # Define the path to save the uploaded file
        media_path = UPLOAD_DIRECTORY / media.filename

        # Save the uploaded file to the local directory
        with open(media_path, "wb") as buffer:
            shutil.copyfileobj(media.file, buffer)

        # Parse the JSON string for coordinates
        parsed_coordinates = json.loads(coordinates)
        
        print(f"Received media file: {media.filename}")
        print(f"Segmentation prompt: {prompt}")
        print(f"Received coordinates: {coordinates}")

        # In a real application, you would call your AI model here,
        # for example: segmented_image = get_segmented_image(media_path, parsed_coordinates)
        # For now, we'll return a success message.
        
        return {
            "message": "Media and prompt received successfully!",
            "file": media.filename,
            "prompt": prompt,
            "coordinates": parsed_coordinates
        }
    except Exception as e:
        print(f"Error handling upload: {e}")
        raise HTTPException(status_code=500, detail="Failed to process request.")

# To run the server, use the command: uvicorn main:app --reload
if __name__ == "__main__":
    uvicorn.run(app, host="192.168.1.5", port=3000)

'''