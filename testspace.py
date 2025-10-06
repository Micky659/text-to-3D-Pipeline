import requests
import json
from openai import OpenAI


LLM_Deep = True

if LLM_Deep:
    client = OpenAI(api_key="sk-d3a04397262d4362b6cbd6fc6b6e5172", base_url="https://api.deepseek.com")

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "This is a test, respond with 3 lines of text"},
        ],
        stream=False
    )

    print(response.choices[0].message.content)
else:
    body = {
        "model": "llama3.1:8b",
        "prompt": "Create a difficult problem for an LLM evaluation that matches the complexity of a layout generation with multiple objects and constraints.",
        # "max_tokens": max_tokens,
        "temperature": 0,
        # If Ollama endpoint expects different names, edit here.
    }
    resp = requests.post("http://localhost:11434/api/generate", json=body, timeout=120)
    resp.raise_for_status()

    responses = []
    for line in resp.iter_lines():
        print(line)
        if line:
            obj = json.loads(line.decode("utf-8"))
            if obj.get("done"):
                break
            responses.append(obj)

    # Join all text parts from the stream
    output = "".join([o["response"] for o in responses])
    print(output)

    start = output.find("{")
    end = output.rfind("}") + 1
    data = output[start:end]

    print(data)