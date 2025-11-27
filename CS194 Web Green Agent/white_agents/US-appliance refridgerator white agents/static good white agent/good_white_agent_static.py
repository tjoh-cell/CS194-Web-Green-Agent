import base64
import os
from flask import Flask, request, jsonify

app = Flask(__name__)

# This helper function reads all .png files from a folder,
# base64-encodes them, and returns them as a list of strings.
def load_screenshots_from_disk(folder_name):
    screenshots = []
    if not os.path.isdir(folder_name):
        print(f"Error: Screenshot folder '{folder_name}' not found.")
        return []
        
    # Sort files to ensure they are in the correct order
    files = sorted(os.listdir(folder_name))
    for filename in files:
        if filename.endswith(".png") or filename.endswith(".jpg"):
            file_path = os.path.join(folder_name, filename)
            try:
                with open(file_path, "rb") as f:
                    # Read the raw bytes, encode to base64, then decode as a string
                    img_bytes = f.read()
                    b64_string = base64.b64encode(img_bytes).decode('utf-8')
                    screenshots.append(b64_string)
            except Exception as e:
                print(f"Error loading screenshot {file_path}: {e}")
    
    print(f"Loaded {len(screenshots)} screenshots from {folder_name}")
    return screenshots

# Static good action history
GOOD_ACTION_HISTORY = [
[
  {
    "command": "NAVIGATE",
    "url": "https://www.us-appliance.com/"
  },
  {
    "command": "CLICK",
    "selector": "text=Refrigerators"
  },
  {
    "command": "CLICK",
    "selector": "text=All Refrigerators"
  },
  {
    "command": "SCROLL",
    "direction": "DOWN"
  },
  {
    "command": "CLICK",
    "selector": "text=Sort By"
  },
  {
    "command": "CLICK",
    "selector": "text=Most Viewed"
  },
  {
    "command": "SCROLL",
    "direction": "DOWN"
  },
  {
    "command": "CLICK",
    "selector": "text=Stainless Steel"
  },
  {
    "command": "SCROLL",
    "direction": "DOWN"
  },
  {
    "command": "CLICK",
    "selector": "text=36"
  },
  {
    "command": "SCROLL",
    "direction": "DOWN"
  },
  {
    "command": "CLICK",
    "selector": "text=4 - 5 stars"
  },
  {
    "command": "END_TASK"
  }
]
]

@app.route('/run_task', methods=['POST'])
def run_task():
    data = request.json
    task_description = data.get('task_description', '')
    
    print("GoodStaticAgent: Returning 'GOOD' trajectory with real screenshots.")
    screenshots = load_screenshots_from_disk("good_run")
    return jsonify({
        "action_history": GOOD_ACTION_HISTORY,
        "screenshots_base64": screenshots
    }), 200

if __name__ == '__main__':
    app.run(port=6001)