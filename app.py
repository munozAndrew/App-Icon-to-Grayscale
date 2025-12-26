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


app = Flask(__name__)


CORS(app) #add origins When frontend is up
BLACK = (0,0,0)
GRAY = (51,51,51)

#ideviceisntaller
def get_app_names():
    
    load_dotenv()
    IDEVICEINSTALLER_PATH = os.getenv('IDEVICEINSTALLER_PATH')
    result = subprocess.run( [IDEVICEINSTALLER_PATH, "list"], capture_output=True, text=True, check=False )
    
    app_names = []
    
    with io.StringIO(result.stdout) as f:
        reader = csv.reader(f)
        
        next(reader, None)
        
        for row in reader:
            #Ensure no dups check manifest
            if len(row) == 3:
                app_names.append( row[2].strip().strip('"'))
            
    return app_names

#itunes
def get_icon_urls():
    app_names = get_app_names()
    url = config.BASE_URL

    icon_urls = []

    for name in app_names:
        
        params = {
        "term" : name,
        "entity" : config.ENTITY,
        "media" : config.MEDIA,
        "country" : config.COUNTRY,
        "limit" : config.LIMIT
        }
        
        delay = 20
        
        try:
            response = requests.get(url, params=params)
            
            if response.status_code == 200:
                icon_url = response.json()
                
                icon_urls.append(icon_url["results"][0]["artworkUrl512"])
            else:
                print("Error: ", response.status_code)
            
        except requests.RequestException as e:
            print("error", e)
    
    return icon_urls, app_names    
    
    
    
def process_icon(app_name, image, target_size=1024):
    
    #img = Image.open(image_file).convert("RGBA")
    img = Image.open(BytesIO(image)).convert("RGBA")

    
    img = img.resize((target_size, target_size), Image.Resampling.LANCZOS)
    
    img_np = np.array(img) #PIL to NP for speedup (hieght, width, 4)
    
    r, g, b, og_a  = img_np[..., 0], img_np[..., 1], img_np[..., 2], img_np[..., 3]
    
    is_icon = (r > 200) & (g > 200) & (b > 200)
    
    out_rgb = np.zeros((target_size, target_size, 3), dtype=np.uint8 )
    
    out_rgb[is_icon] = GRAY
    out_rgb[~is_icon] = BLACK
    
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
    

@app.route("/process", methods=["GET"])
def return_icons_endpoint():
    
    icon_urls, app_names = get_icon_urls()
        
    now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    dir_path = Path("Storage", now)
    dir_path.mkdir(parents=True, exist_ok=True)
    

    for icon_url, app_name in zip(icon_urls, app_names):
        response = requests.get(icon_url)
        response.raise_for_status()
                
            
        try:
            #ensure format patches whats returned
            processed_img = process_icon(app_name, response.content, target_size=1024)
            
            file_path = dir_path / f"{app_name}_dark.png"
            processed_img.save(file_path, format="PNG")  
            
            
        except Exception as e:
            print("Error: ", e)
            return jsonify({"error": str(e)}), 500
    
    
    zip_path = Path("Storage", f"{now}.zip")
    
    zipped_dir(zip_path, dir_path)
    
    return send_file(
        f"{now}.zip",
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"{now}.zip"
    )
    
 
@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "mmm", "service": "icon-gen"})       
        
if __name__ == "__main__":
    print("Server on 5000")
    app.run(debug=True, host="0.0.0.0", port=5000)