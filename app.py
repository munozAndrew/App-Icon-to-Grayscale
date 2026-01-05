from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from PIL import Image
import io
import numpy as np
import subprocess
import csv
import requests
from dotenv import load_dotenv
import os
import config
from io import BytesIO
from datetime import datetime
from pathlib import Path
import zipfile
import random
import time
import uuid
import threading 
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

app = Flask(__name__)

session = requests.Session()
retries = Retry(total=5, backoff_factor=2, status_forcelist=[500, 502, 503, 504, 429], allowed_methods=["GET"], raise_on_status=False)
#depending on read / Status / connection retries

adapter = HTTPAdapter(max_retries=retries, pool_connections=1, pool_maxsize=1)
session.mount("https://", adapter)
session.mount("http://", adapter)

CORS(app) #add origins When frontend is up
EDGE_COLOR = config.EDGE_COLOR
ICON_COLOR = config.ICON_COLOR
jobs = {} # job_id: {status: , zip_path: , timestamp: }

#ideviceisntaller
def get_icons():
    
    load_dotenv()
    IDEVICEINSTALLER_PATH = os.getenv('IDEVICEINSTALLER_PATH')
    result = subprocess.run( [IDEVICEINSTALLER_PATH, "list"], capture_output=True, text=True, check=False )
    #print(result)
    
    app_urls = []
    app_names = []
    
    with io.StringIO(result.stdout) as f:
        reader = csv.reader(f)
        
        next(reader, None)
        
        for row in reader:
            #Ensure no dups check manifest
            if len(row) == 3:
                app_name = row[2].strip().strip('"')
                
                #print("Current App Name:", app_name)
                #print("repr:", repr(app_name))
                #print("chars:", [hex(ord(c)) for c in app_name])
                
                icon_url = fetch_icon_url(app_name)
                
                if icon_url:
                    app_names.append(app_name)
                    app_urls.append(icon_url)
                else:
                    print(f"Skipping {app_name}: no Icon URL")
            
    return app_urls, app_names

def fetch_icon_url(app_name):
    
    url = config.BASE_URL
    delay = 4
    print(app_name)
    
    params = {
            "term" : app_name,
            "entity" : config.ENTITY,
            "media" : config.MEDIA,
            "country" : config.COUNTRY,
            "limit" : config.LIMIT
            }    
    
        
    try:
        response = session.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            raw_data = response.json()
            
            if app_name == "Pass&Docs":
                print(raw_data)
            
            if raw_data["results"]:
                return raw_data["results"][0]["artworkUrl512"]
            
            return None
            
        response.raise_for_status()
        
    except requests.RequestException as e:
        print("error", e)
    
    raise RuntimeError(f"Failed to fetch icon URL for {app_name}")
    
def process_icon(app_name, image, target_size=1024):
    
    #img = Image.open(image_file).convert("RGBA")
    img = Image.open(BytesIO(image)).convert("RGBA")

    
    img = img.resize((target_size, target_size), Image.Resampling.LANCZOS)
    
    img_np = np.array(img) #PIL to NP for speedup (hieght, width, 4)
    
    r, g, b, og_a  = img_np[..., 0], img_np[..., 1], img_np[..., 2], img_np[..., 3]
    
    is_icon = (r > 200) & (g > 200) & (b > 200)
    
    out_rgb = np.zeros((target_size, target_size, 3), dtype=np.uint8 )
    
    out_rgb[is_icon] = ICON_COLOR
    out_rgb[~is_icon] = EDGE_COLOR
    
    final_img = np.dstack([out_rgb, og_a])
    

    
    return Image.fromarray(final_img, mode="RGBA")

def zipped_dir(zip_path, dir_path):
    
    #try ZIP_STORED
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        
        #expandable in the future
        #think Sectioning based on App details
        for root, dirs, files in os.walk(dir_path):
            
            for file in files: 
                full_path = os.path.join(root, file)
                arcname = os.path.relpath(full_path, dir_path) # storage/MMHHDD/insta.png -> insta.png
                z.write(full_path, arcname)
    
def run_generate_job(job_id):
    try:
        jobs[job_id]["status"] = "in_progress"
        icon_urls, app_names = get_icons()
        
        print("Drafting Icons now...")
            
        jobs[job_id]["timestamp"] = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        dir_path = Path("Storage", job_id)
        dir_path.mkdir(parents=True, exist_ok=True)
        
        
        

        for icon_url, app_name in zip(icon_urls, app_names):
            response = session.get(icon_url, timeout=10)
            response.raise_for_status()
                    
            try:
                #ensure format patches whats returned
                processed_img = process_icon(app_name, response.content, target_size=1024)
                
                file_path = dir_path / f"{app_name}_dark.png"
                processed_img.save(file_path, format="PNG")  
                
                
            except Exception as e:
                print("Error: ", e)
                #jobs[job_id]["status"] = "failed"
                continue
        
        filename = f"{job_id}_{jobs[job_id]['timestamp']}.zip"
        zip_path = Path("Storage", filename)
        zipped_dir(zip_path, dir_path)

        jobs[job_id]['zip_path'] = str(zip_path)
        jobs[job_id]['status'] = "completed"

        
    except Exception as e:
        print("Job Error: ", e)
        jobs[job_id]["status"] = "failed"
           
@app.route("/generate", methods=["POST"])
def generate():
    
    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "queued", "zip_path": None, "timestamp": None}

    thread = threading.Thread(target=run_generate_job, args=(job_id,), daemon=True)
    thread.start()
    
    return jsonify({"job_id": job_id}), 202


@app.route("/status/<job_id>", methods=["GET"])
def job_status(job_id):
    job = jobs.get(job_id)
    if job:
        return jsonify({ "job_id": job_id, "status": job["status"]})
    else:
        return jsonify({"error": "Job ID not found"}), 404

@app.route("/result/<job_id>", methods=["GET"])
def job_result(job_id):
    job = jobs.get(job_id)
    if job and job["status"] == "completed":
        return send_file(
            Path(job['zip_path']),
            mimetype="application/zip",
            as_attachment=True,
            download_name=f"{job['timestamp']}.zip"
        )
        
    else:
        return jsonify({"error": "Job not completed or not found"}), 404

@app.route("/downloaded/<job_id>", methods=["POST"])
def job_downloaded(job_id):
    job = jobs.get(job_id)
    if job:
        del jobs[job_id]
        return jsonify({"message": "Job data cleaned up"}), 200
    else:
        return jsonify({"error": "Job ID not found"}), 404
    
 
@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "mmm", "service": "icon-gen"})       
        
if __name__ == "__main__":
    print("Server on 5000")
    app.run(debug=True, host="0.0.0.0", port=5000)