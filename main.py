#Script to Start FastAPI Backend - uvicorn main:app --reload --host 0.0.0.0 --port 8000
#Import libraries
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import pandas as pd
import os
from typing import List
from uuid import uuid4

#Initialize FastAPI app
app = FastAPI(
    title="AngaraiThrive Backend",
    description="Uploading and Accessing CSV",
)
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads") #Sets directory name where uplaoded CSVs are stored
os.makedirs(UPLOAD_DIR, exist_ok=True) #Declares Directory

@app.post("/upload-csv") #Command to trigger upload_csv function - A function that adds the csv to uploads directory
async def upload_csv(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".csv"): #Checking if file is csv by looking at file extension
        raise HTTPException(status_code=400, detail="Only CSV files are supported.") #Error message when file isn't csv
    unique_id = uuid4().hex #Setting unique id
    filename = f"{unique_id}_{file.filename}" #Setting filename for the uplaoded csv with unique id and original file name
    file_path = os.path.join(UPLOAD_DIR, filename) #Seting path of upload to the uploads folder
    try:
        contents = await file.read() #Reads the file
        with open(file_path, "wb") as f: #Opens a new file with dynamic assignment to vairable f
            f.write(contents) #Writes the contents of the file and file name to f
    except Exception as e: 
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}") #Error message for other exception

    return {"filename": filename} #returns the filename

@app.get("/csv-files") #Command to trigger list_csv_files - A function that gets all csvs from uploads directory
async def list_csv_files():
    files = [f for f in os.listdir(UPLOAD_DIR) if f.lower().endswith(".csv")] #Creating list of files from the uploads directory that are CSVs
    return {"files": files} #Returns list of files

@app.get("/csv/{filename}") #Command to trigger read_csv - A function that gets a specfic csv from uploads directory
async def read_csv(filename: str):
    file_path = os.path.join(UPLOAD_DIR, filename) #assigns filepath of the argument to file_path
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found.") #Error displayed if file doesn't exist
    try:
        df = pd.read_csv(file_path) #Uses pandas to read the csv
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading CSV: {e}") #Error when pandas is not able to read the file

    records = df.to_dict(orient="records") #Converts csv to JSON Dictionary for sentiment analysis with horizontal rows being records
    return JSONResponse(content={"columns": df.columns.tolist(), "records": records}) #returns JSON dictionary version of the csv
