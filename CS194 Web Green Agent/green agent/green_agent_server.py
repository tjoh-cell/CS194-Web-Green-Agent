import os
import re
import json
import requests
import base64
import io
import google.generativeai as genai
from flask import Flask, request, jsonify
from PIL import Image
from datasets import load_dataset

# --- Configuration ---
app = Flask(__name__)
OM2W_TASKS = {}
TASKS_FILE_NAME = "tasks.json"
global_run_counter = 0

# Configure the Gemini API client
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
text_model = genai.GenerativeModel('gemini-2.0-flash-lite')
vision_model = genai.GenerativeModel('gemini-2.0-flash-lite')
SCREENSHOT_THRESHOLD = 4 

# --- Helper Functions ---

def load_om2w_tasks():
    """Loads tasks from the Hugging Face Hub."""
    global OM2W_TASKS
    try:
        # Load the dataset, specifically the tasks.json file
        # Note: This is a gated dataset. You MUST be logged in to the
        # Hugging Face CLI (`huggingface-cli login`) and have
        # accepted the terms on the dataset's page.
        print("Loading 'osunlp/Online-Mind2Web' from Hugging Face...")
        dataset = load_dataset(
            "osunlp/Online-Mind2Web", 
            split="test", 
            download_mode="force_redownload"
        )
        
        for task in dataset:
            # We key the tasks by their 'task_id' for easy lookup
            OM2W_TASKS[task['task_id']] = task 
        
        print(f"Successfully loaded {len(OM2W_TASKS)} tasks from Hugging Face.")
    
    except Exception as e:
        print(f"--- FAILED TO LOAD DATASET ---")
        print(f"Error: {e}")
        print("\nPlease ensure you have installed the 'datasets' library: pip install datasets")
        print("This is a GATED dataset. You MUST:")
        print("1. Log in to the Hugging Face CLI on this machine: `huggingface-cli login`")
        print("2. Accept the terms on the dataset's Hugging Face page.")
        print("---------------------------------")
        OM2W_TASKS = {}

# parse_key_points, parse_screenshot_score, parse_final_status,

def parse_key_points(response_text):
    """
    Parses key points from the LLM response, filtering out
    any lines that are just headers.
    """
    print(f"DEBUG (Key Points Raw Response):\n---\n{response_text}\n---")
    key_points = []
    lines = response_text.strip().splitlines()
    
    # A list of header strings to ignore, in lowercase
    ignore_headers = [
        "**key points**:", 
        "**key points**",
        "key points:",
        "key points"
    ]

    for line in lines:
        stripped_line = line.strip()
        
        if not stripped_line:
            continue # Skip empty lines
            
        # Check if the line is just a header
        if stripped_line.lower() in ignore_headers:
            print(f"DEBUG: Ignoring header line: {stripped_line}")
            continue
            
        # If it's not a header and not empty, append it
        key_points.append(stripped_line.lstrip('0123456789.- '))

    print(f"DEBUG (Parsed Key Points): {key_points}")
    return key_points

def parse_screenshot_score(response_text):
    """
    Parses 'Reasoning:' and 'Score:' from the LLM's Step 2 response.
    Fixed to avoid false positives from numbers in the text body.
    """
    reasoning = "No reasoning found."
    score = 0
    
    # 1. Parse Reasoning
    try:
        # Look for "Reasoning", match everything until we hit the "Score" label or end of string
        reason_match = re.search(r"Reasoning[\W_]+(.*?)(?=\n\s*[-*]*\s*Score)", response_text, re.DOTALL | re.IGNORECASE)
        if reason_match:
            reasoning = reason_match.group(1).strip()
        else:
            # Fallback if the lookahead fails, just grab until the end
            reason_match_loose = re.search(r"Reasoning[\W_]+(.*)", response_text, re.DOTALL | re.IGNORECASE)
            if reason_match_loose:
                reasoning = reason_match_loose.group(1).strip()
    except Exception:
        pass

    # 2. Parse Score
    try:
        all_matches = re.findall(r"Score[^\d]*:\s*(\d+)", response_text, re.IGNORECASE)
        
        if all_matches:
            # Take the LAST match found (-1). 
            # The actual score is always at the very bottom of the LLM response.
            score = int(all_matches[-1])
        else:
            # Fallback: If absolutely no colon is found, look for "Score" at the very end of the string
            end_match = re.search(r"Score\D*(\d+)\s*$", response_text, re.IGNORECASE)
            if end_match:
                score = int(end_match.group(1))

    except Exception as e:
        print(f"DEBUG (parse_screenshot_score): Failed to parse score. Error: {e}")
        
    return reasoning, score

def parse_final_status(response_text):
    """
    Parses the 'Status:' line from the LLM's Step 3 response.
    Handles responses with or without quotes.
    """
    try:
        match = re.search(r"Status:\s*\"?(success|failure)\"?", response_text, re.IGNORECASE)
        if match:
            return match.group(1).lower()
    except Exception as e:
        print(f"DEBUG (parse_final_status): Regex failed with {e}")

    # Fallback for the original strict check, just in case
    if 'Status: "failure"' in response_text:
        return "failure"
    if 'Status: "success"' in response_text:
        return "success"
        
    print("DEBUG (parse_final_status): Could not find status, defaulting to failure.")
    return "failure"

def parse_final_thoughts(response_text):
    """
    Parses the 'Thoughts:' block from the LLM's Step 3 response.
    """
    try:
        match = re.search(r"Thoughts:(.*?)Status:", response_text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
    except Exception as e:
        print(f"DEBUG (parse_final_thoughts): Regex failed with {e}")

    # Fallback if regex fails or "Status:" isn't found
    if "Thoughts:" in response_text:
        return response_text.split("Thoughts:")[1].strip()
        
    return "No 'Thoughts:' block was found in the LLM response."

def base64_to_pil(base64_str):
    image_data = base64.b64decode(base64_str)
    image = Image.open(io.BytesIO(image_data))
    return image

def llm_call_step_1(task_description):
    prompt = PROMPT_STEP_1.replace("(task)", task_description)
    response = text_model.generate_content(prompt)
    key_points = parse_key_points(response.text)
    return key_points

def llm_call_step_2(task_description, key_points, screenshot_image_base64):
    """Step 2: Key Screenshot Identification (Multimodal)"""
    key_points_str = "\n".join(key_points)
    prompt_text = PROMPT_STEP_2.replace("(task)", task_description)
    prompt_text = prompt_text.replace("(key points)", key_points_str)
    
    pil_image = base64_to_pil(screenshot_image_base64)
    
    response = vision_model.generate_content([prompt_text, pil_image])
    response_text = response.text

    # DEBUG LOG
    print(f"DEBUG (Step 2 Raw Response):\n---\n{response_text}\n---")
    # ---------------------------------
    
    reasoning, score = parse_screenshot_score(response_text)
    return reasoning, score

def llm_call_step_3(task_description, key_points, action_history, key_screenshots_with_reasons):
    key_points_str = "\n".join(key_points)
    action_history_str = "\n".join([str(a) for a in action_history])
    screenshots_str = "\n".join([f"Screenshot: {s['reasoning']}" for s in key_screenshots_with_reasons])

    # DEBUG LOG
    print("\n--- Sending to WebJudge (Step 3) ---")
    print(f"Key Points:\n{key_points_str}")
    print(f"Action History:\n{action_history_str}")
    print(f"Screenshots Info:\n{screenshots_str}")
    print("------------------------------------\n")
    # ----------------------------------
    
    prompt = PROMPT_STEP_3.replace("(task)", task_description)
    prompt = prompt.replace("(key points)", key_points_str)
    prompt = prompt.replace("(action history]", action_history_str) 
    prompt = prompt.replace("(thoughts)", screenshots_str)
    
    response = text_model.generate_content(prompt)
    response_text = response.text
    
    # Debug Log for Raw Response
    print(f"\n--- WebJudge (Step 3) RAW RESPONSE ---:\n{response_text}\n----------------------------------\n")

    # Call both parsers to get both pieces of information
    status = parse_final_status(response_text)
    thoughts = parse_final_thoughts(response_text)
    
    return status, thoughts # Return a tuple with both
    # -----------------------

# --- A2A Endpoint ---

@app.route('/start_assessment', methods=['POST'])
def start_assessment():
    if not OM2W_TASKS:
        load_om2w_tasks()
        if not OM2W_TASKS:
             return jsonify({"error": "No tasks loaded. Check server logs for Hugging Face auth errors."}), 500

    data = request.json
    task_id = data.get('task_id')
    participant_url = data.get('participant_url')

    if not task_id or not participant_url:
        return jsonify({"error": "Missing 'task_id' or 'participant_url'"}), 400
        
    task = OM2W_TASKS.get(task_id)
    if not task:
        return jsonify({"error": f"Task ID '{task_id}' not found in loaded dataset."}), 404
    
    # The task object from HF is a dict, we just need the description
    task_description = task['confirmed_task']
    start_url = task['website']
    
    print(f"--- Starting Assessment for: {participant_url} ---")
    print(f"Task ID: {task_id}")
    print(f"Task: {task_description}")

    # STEP 1: KEY POINT IDENTIFICATION
    print("Step 1: Identifying Key Points...")
    key_points = llm_call_step_1(task_description)
    print(f"Key Points: {key_points}")

    # Trigger the White Agent
    try:
        response = requests.post(f"{participant_url}/run_task", 
                                 json={
                                     "task_description": task_description,
                                     "start_url": start_url
                                     },
                                 timeout=300) 
        trajectory = response.json()
        action_history = trajectory["action_history"]
        screenshots_base64 = trajectory["screenshots_base64"]

        # Debug log
        print("\n--- White Agent Trajectory Received ---")
        print(json.dumps(action_history, indent=2))
        print(f"Received {len(screenshots_base64)} screenshots.")
        print("---------------------------------------\n")

        # --- SCREENSHOT LOGGING ---
        global global_run_counter
        run_folder = f"_run_{global_run_counter}"
        os.makedirs(run_folder, exist_ok=True)
        print(f"Saving {len(screenshots_base64)} screenshots to '{run_folder}'...")
        
        for i, b64_string in enumerate(screenshots_base64):
            try:
                # Decode the base64 string
                image_data = base64.b64decode(b64_string)
                file_path = os.path.join(run_folder, f"step_{i}.png")
                # Save the image
                with open(file_path, 'wb') as f:
                    f.write(image_data)
            except Exception as e:
                print(f"  Error saving screenshot {i}: {e}")
        
        global_run_counter += 1
        # --- END LOGGING ---

    except Exception as e:
        print(f"Failed to run white agent: {e}")
        return jsonify({"webjudge_status": "failure", "reason": f"White agent at {participant_url} failed to respond."}), 500

    # STEP 2: KEY SCREENSHOT IDENTIFICATION
    print("Step 2: Identifying Key Screenshots... (Now logging thoughts)")
    key_screenshots_with_reasons = []
    
    for i, screenshot_b64 in enumerate(screenshots_base64):
        print(f"\n--- Analyzing Screenshot {i} ---")
        
        # This handles the case where the list might contain raw bytes
        if not isinstance(screenshot_b64, str):
             try:
                buffered = io.BytesIO()
                screenshot_b64.save(buffered, format="PNG")
                img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
             except Exception as e:
                print(f"  Error encoding screenshot {i}: {e}")
                continue
        else:
             img_str = screenshot_b64

        # Call the Step 2 LLM
        reasoning, score = llm_call_step_2(task_description, key_points, img_str)
        
        # DEBUG LOG
        print(f"Screenshot {i} Reasoning: {reasoning}")
        print(f"Screenshot {i} Score: {score}")
        # ----------------------------------------

        if score >= SCREENSHOT_THRESHOLD:
            print(f"  > This screenshot PASSED (Score >= {SCREENSHOT_THRESHOLD})")
            key_screenshots_with_reasons.append({"reasoning": reasoning, "score": score})
            
    print(f"\nFound {len(key_screenshots_with_reasons)} key screenshots (Score >= {SCREENSHOT_THRESHOLD}).")

    # STEP 3: OUTCOME JUDGEMENT
    print("Step 3: Making Outcome Judgement...")
    
    # Unpack the new tuple (status, thoughts)
    final_status, final_thoughts = llm_call_step_3(task_description, 
                                     key_points, 
                                     action_history, 
                                     key_screenshots_with_reasons)
    
    # This will print the LLM judge's thoughts
    print("\n--- WebJudge (Step 3) Final Parsed Thoughts ---")
    print(final_thoughts)
    print("-----------------------------------------------\n")
    # ---------------------
    
    print(f"--- Assessment Complete. Status: {final_status} ---")
    
    return jsonify({
        "webjudge_status": final_status,
        "webjudge_thoughts": final_thoughts,
        "task_id": task_id,
        "key_points_identified": key_points,
        "key_screenshots_count": len(key_screenshots_with_reasons),
    })

@app.route('/list_tasks', methods=['GET'])
def list_tasks():
    """A simple endpoint to list all loaded task IDs and descriptions."""
    if not OM2W_TASKS:
        load_om2w_tasks()
        if not OM2W_TASKS:
            return jsonify({"error": "Failed to load tasks."}), 500
            
    # Create a simple list of tasks to send back
    task_list = [
        {
            "task_id": tid, 
            "task_description": task['confirmed_task'],
            "website": task['website']
        } 
        for tid, task in OM2W_TASKS.items()
    ]
    
    return jsonify(task_list)

if __name__ == '__main__':    
    # Load tasks on startup
    # PROMPT 1:"
    PROMPT_STEP_1 = """
    You are an expert tasked with analyzing a given task to identify the key points explicitly
    stated in the task description.
    **Objective**: Carefully analyze the task description and extract the critical elements
    explicitly mentioned in the task for achieving its goal.
    **Instructions**:
    1. Read the task description carefully.
    2. Identify and extract **key points** directly stated in the task description.
    - A **key point** is a critical element, condition, or step explicitly mentioned in the task
    description.
    - Do not infer or add any unstated elements.
    - Words such as "best," "highest," "cheapest," "latest," "most recent," "lowest," "closest," "highest-
    rated," "largest," and "newest" must go through the sort function (e.g., the key point should be
    "Filter by highest").
    **Respond with**:
    - **Key Points**: A numbered list of the explicit key points for completing this task, one per
    line, without explanations or additional details.
    Task: (task)
    """

    # PROMPT 2:"
    PROMPT_STEP_2 = """
    You are an expert evaluator tasked with determining whether an image contains information
    about the necessary steps to complete a task.
    **Objective**: Analyze the provided image and decide if it shows essential steps or evidence
    required for completing the task.
    Use your reasoning to explain your decision before assigning
    a score.
    **Instructions**:
    1. Provide a detailed description of the image, including its contents, visible elements, text (if
    any), and any notable features.
    2. Carefully examine the image and evaluate whether it contains necessary steps or evidence
    crucial to task completion:
    - Identify key points that could be relevant to task completion, such as actions, progress
    indicators, tool usage, applied filters, or step-by-step instructions.
    - Does the image show actions, progress indicators, or critical information directly related to
    completing the task?
    - Is this information indispensable for understanding or ensuring task success?
    - If the image contains partial but relevant information, consider its usefulness rather than
    dismissing it outright.
    3. Provide your response in the following format:
    - **Reasoning**: [Your explanation]
    **Score**: [1-5]
    **Task**: (task)
    **Key Points for Task Completion**: (key points)
    The snapshot of the web page is shown in the image.
    """

    # PROMPT 3:"
    PROMPT_STEP_3 = """
    You are an expert in evaluating the performance of a web navigation agent.
    The agent is
    designed to help a human user navigate a website to complete a task.
    Given the user's task,
    the agent's action history, key points for task completion, some potentially important web
    pages in the agent's trajectory and their reasons, your goal is to determine whether the agent
    has completed the task and achieved all requirements.
    Your response must strictly follow the following evaluation criteria!
    *Important Evaluation Criteria*:
    1: The filtered results must be displayed correctly. If filters were not properly applied
    (i.e., missing selection, missing confirmation, or no visible effect in results), the task is not
    considered successful.
    2: You must carefully check whether these snapshots and action history meet these key points.
    Ensure that specific filter conditions, such as "best," "highest," "cheapest," "latest," "most
    recent," "lowest," "closest," "highest-rated," "largest," and "newest" are correctly applied using
    the filter function (e.g., sort function).
    3: Certain key points or requirements should be applied by the filter.
    Otherwise, a search with
    all requirements as input will be deemed a failure since it cannot guarantee that all results
    meet the requirements!
    4: If the task requires filtering by a specific range of money, years, or the number of beds and
    bathrooms, the applied filter must exactly match the given requirement.
    Any deviation results
    in failure. To ensure the task is successful, the applied filter must precisely match the specified
    range without being too broad or too narrow.
    Examples of Failure Cases:
    - If the requirement is less than \$50, but the applied filter is less than \$25, it is a failure.
    - If the requirement is \$1500-\$2500, but the applied filter is \$2000-\$2500, it is a failure.
    - If the requirement is \$25-\$200, but the applied filter is \$0-\$200, it is a failure.
    - If the required years are 2004-2012, but the applied filter is 2001-2012, it is a failure.
    - If the required years are before 2015, but the applied filter is 2000-2014, it is a failure.
    - If the task requires exactly 2 beds, but the filter applied is 2+ beds, it is a failure.
    5: Some tasks require a submission action or a display of results to be considered successful.
    6: If the retrieved information is invalid or empty (e.g., No match was found), but the agent
    has correctly performed the required action, it should still be considered successful.
    7: If the current page already displays all available items, then applying a filter is not
    necessary.
    As long as the agent selects items that meet the requirements (e.g., the cheapest or
    lowest price), the task is still considered successful.
    *IMPORTANT*
    Format your response into two lines as shown below:
    Thoughts: <your thoughts and reasoning process based on double-checking each key points
    and the evaluation criteria>
    Status: "success" or "failure"
    User Task: (task)
    Key Points: (key points)
    Action History: (action history]
    The potentially important snapshots of the webpage in the agent's trajectory and their reasons:
    (thoughts)
    """

    load_om2w_tasks() 
    app.run(port=5001, debug=True)
