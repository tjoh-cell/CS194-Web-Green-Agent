import base64
import os
from flask import Flask, request, jsonify

app = Flask(__name__)

def load_screenshots_from_disk(folder_name):
    screenshots = []
    if not os.path.isdir(folder_name):
        print(f"Error: Screenshot folder '{folder_name}' not found.")
        return []
    files = sorted(os.listdir(folder_name))
    for filename in files:
        if filename.endswith(".png") or filename.endswith(".jpg"):
            file_path = os.path.join(folder_name, filename)
            try:
                with open(file_path, "rb") as f:
                    img_bytes = f.read()
                    b64_string = base64.b64encode(img_bytes).decode('utf-8')
                    screenshots.append(b64_string)
            except Exception as e:
                print(f"Error loading screenshot {file_path}: {e}")
    print(f"Loaded {len(screenshots)} screenshots from {folder_name}")
    return screenshots

# Static careless action history
CARELESS_ACTION_HISTORY = [
  {
    "command": "NAVIGATE",
    "url": "https://www.ign.com/"
  },
  {
    "command": "CLICK",
    "selector": "text=Reviews"
  },
  {
    "command": "CLICK",
    "selector": "text=Editor's Choice"
  },
  {
    "command": "SCROLL",
    "direction": "DOWN"
  },
  {
    "command": "CLICK",
    "selector": "text=Games"
  },
  {
    "command": "CLICK",
    "selector": "text= All Genres"
  },
  {
    "command": "CLICK",
    "selector": "text=Board"
  },
  {
    "command": "CLICK",
    "direction": "text= All Scores"
  },
  {
    "command": "CLICK",
    "selector": "text=8.0 - 8.9"
  },
    {"command": "END_TASK"}
]

@app.route('/run_task', methods=['POST'])
def run_task():
    data = request.json
    task_description = data.get('task_description', '')
    
    print("CarelessStaticAgent: Returning 'CARELESS' trajectory with real screenshots.")
    screenshots = load_screenshots_from_disk("careless_run")
    return jsonify({
        "action_history": CARELESS_ACTION_HISTORY,
        "screenshots_base64": screenshots
    }), 200

if __name__ == '__main__':
    app.run(port=6002)