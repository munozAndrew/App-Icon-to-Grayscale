from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from PIL import Image
import io
import numpy as np

app = Flask(__name__)


CORS(app) #add origins When frontend is up
BLACK = (0,0,0)
GRAY = (51,51,51)


def process_icon(image_file, target_size=1024):
    
    img = Image.open(image_file).convert("RGBA")
    img = img.resize((target_size, target_size), Image.Resampling.LANCZOS)
    
    img_np = np.array(img) #PIL to NP for speedup (hieght, width, 4)
    
    r, g, b, og_a  = img_np[..., 0], img_np[..., 1], img_np[..., 2], img_np[..., 3]
    
    is_icon = (r > 200) & (g > 200) & (b > 200)
    
    out_rgb = np.zeros((target_size, target_size, 3), dtype=np.uint8 )
    
    out_rgb[is_icon] = GRAY
    out_rgb[~is_icon] = BLACK
    
    final_img = np.dstack([out_rgb, og_a])
    
    return Image.fromarray(final_img, mode="RGBA")

 
@app.route("/process-icon", methods=["POST"])
def process_icon_endpoint():
    try:
        if "icon" not in request.files:
            print("STUCK")
            return jsonify({"error":"Noicon file provided"}), 400

        file = request.files["icon"]
        
        if file.filename == "":
            return jsonify({"error":"Nofilename provided"}), 400
        
        processed_img = process_icon(file, target_size=1024)
        
        img_io = io.BytesIO()
        processed_img.save(img_io, "PNG", optimize=True)
        img_io.seek(0)
        
        return send_file(img_io, mimetype="image/png")        
        
        
    except Exception as e:
        print("Error: ", e)
        return jsonify({"error": str(e)}), 500
    
    
    
if __name__ == "__main__":
    print("Server on 5000")
    app.run(debug=True, host="0.0.0.0", port=5000)