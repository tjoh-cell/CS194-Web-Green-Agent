To get started, first clone the repository. After cloning, make sure to install flask, google-generativeai, requests, Pillow, datasets, and huggingface_hub (these are in requirements.txt). Then configure your gemini API key as an environment variable and name it "GOOGLE_API_KEY" (My implementation uses gemini-2.0-flash-lite which is free). After installing huggingface, create a hugging face account (https://huggingface.co/), then visit https://huggingface.co/datasets/osunlp/Online-Mind2Web and accept the data sets TOS, then go to Hugging Face Settings > Access Tokens and create a new token (type: Read), copy that token (hf_...) and in a new terminal type

> huggingface-cli login

and enter your access token when prompted. Once this is set up, open a terminal and navigate to '.\CS194 Web Green Agent\green agent\' and launch the green agent by typing

> python .\green_agent_server.py

As a side note, once you've launched the green agent you can view the tasks loaded by the green agent by opening up a browser and navigating to http://127.0.0.1:5001/list_tasks, although I only have white agents set up for the refrigerator and IGN task, which I will provide commands below to run. Once the green agent is running, open another terminal and navigate to '.\CS194 Web Green Agent\white_agents\'. Once here, there are two test white agents for two tasks: one set for an IGN review task, and other set for a refrigerator task. You can choose either set but you cannot host two careless or two good agents at the same time (both good agents are hosted at port 6001 and both careless agents at port 6002, so you can only host one of each). WHichever task you choose to test, navigate to their respective folder and type

> python .\good_white_agent_static.py

for the good white agent or

> python .\careless_white_agent_static.py

for the careless white agent. If you want to run both, you'll need a terminal for each. Finally, open up one final terminal and type (for windows terminal)

curl.exe --% -X POST http://127.0.0.1:5001/start_assessment -H "Content-Type: application/json" -d "{\\"task_id\\": \\"b7258ee05d75e6c50673a59914db412e_110325\\", \\"participant_url\\": \\"http://127.0.0.1:6001\\"}"

To run the good white agent for the refrigerator task (make sure you're hosting the good white agent for the refrigerator task), or

curl.exe --% -X POST http://127.0.0.1:5001/start_assessment -H "Content-Type: application/json" -d "{\"task_id\": \"b7258ee05d75e6c50673a59914db412e_110325\", \"participant_url\": \"http://127.0.0.1:6002\"}" 

To run the carless white agent for the refrigerator task (likewise make sure the careless white agent for the refrigerator task is running), or if you want to test the IGN review task do these commands respectively.

curl.exe --% -X POST http://127.0.0.1:5001/start_assessment -H "Content-Type: application/json" -d "{\"task_id\": \"aa4b5cb7114fcc138ade82b4b9716d24\", \"participant_url\": \"http://127.0.0.1:6001\"}"

curl.exe --% -X POST http://127.0.0.1:5001/start_assessment -H "Content-Type: application/json" -d "{\"task_id\": \"aa4b5cb7114fcc138ade82b4b9716d24\", \"participant_url\": \"http://127.0.0.1:6002\"}".

The task ID for the refrigerator task is b7258ee05d75e6c50673a59914db412e_110325, and the task id for the IGN review isaa4b5cb7114fcc138ade82b4b9716d24. Like I mentioned previously the host urls for the good and careless agent are http://127.0.0.1:6001, and http://127.0.0.1:6002 respectively. For Mac the command is

curl -X POST http://127.0.0.1:5001/start_assessment \
-H "Content-Type: application/json" \
-d '{"task_id": "[task id]", "participant_url": "[host url]"}'


These commands should replicate the results of the original benchmark

