import subprocess
import os

python_exec = "C:\\Users\\koth_ak\\Akshat's Thesis\\text-to-3D-Pipeline\\.venv\\Scripts\\python.exe"

# List of 10 scene prompts
prompts = [
    "A bathroom with a bathtub, a cabinet for storage, and a trash bin near the corner.",
    "A modern kitchen setup with a stove, a microwave, a dishwasher, and a cabinet along one side.",
    "A laundry room with a washing machine, a cabinet above it, a basket on the floor, and a trash bin next to the washer.",
    "A comfortable bedroom with a bed, a pillow on top, a lamp beside the bed, and a bookshelf in the corner.",
    "A garage interior with a car, a motorcycle, a cabinet for tools, and a trash bin near the back wall.",
    "A waiting room with benches, lamps in the corner, and a flowerpot next to the bench.",
    "A conference room with two tables in the center and a few chairs arranged around them.",
    "A cafe with four sets of tables and two chairs per table.",
    "A sidewalk scene with a bench, a lamp on one side, and a trashcan on the other side.",
    "A small living room with a sofa, a coffee table in front, a lamp beside the sofa, and a pillow on the sofa.",
    "A kitchen countertop with a microwave, a stove, a dishwasher, and a basket.",
    "A dining room with a table in the center, a few chairs around it, and a lamp above the table.",
    "A modern office setup with a table, file cabinet, a printer, and a chair in front of the table."
]



# Define the variations to test
texture_modes = ["gen_and_map"]
llm_mode = "ollama"

# Loop through each prompt and texture mode
for i, text in enumerate(prompts, start=1):
    for texture_mode in texture_modes:
        print(f"\n🚀 Running scene {i} with texture mode '{texture_mode}'...\n")

        # Construct the command
        cmd = [
            python_exec, "run.py",
            "--text", text,
            "--llm_mode", llm_mode,
            "--texture_mode", texture_mode
        ]
        env = os.environ.copy()
        # Execute the command
        subprocess.run(cmd)
