import requests
from typing import Dict, Any
import json
from openai import OpenAI
from .config import settings

class LLMClient:
    def __init__(self, llm_mode: str, ollama_model: str):
        self.base_url_ollama = settings.LLM_BASE_URL_OLLAMA
        self.base_url_deepseek = settings.LLM_BASE_URL_DEEPSEEK
        self.model = ollama_model if ollama_model else settings.LLM_MODEL
        self.deepseek_key = settings.DEEPSEEK_KEY
        self.llm_mode = llm_mode

    def generate(self, prompt: str, max_tokens: int = 1024, temperature: float = 0, model: str = "deepseek-chat") -> str:

        if self.llm_mode=="deepseek":
            client = OpenAI(api_key=self.deepseek_key, base_url=self.base_url_deepseek)

            response = client.chat.completions.create(
                model= model,
                # model="deepseek-reasoner",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant"},
                    {"role": "user",
                     "content": prompt},
                ],
                stream=False
            )

            output = response.choices[0].message.content

            return str(output)

        elif self.llm_mode=='ollama':
            body = {
                "model": self.model,
                "prompt": prompt,
                # "max_tokens": max_tokens,
                "temperature": temperature,
            }
            resp = requests.post(self.base_url_ollama, json=body, timeout=120)
            resp.raise_for_status()

            responses = []
            for line in resp.iter_lines():
                if line:
                    obj = json.loads(line.decode("utf-8"))
                    if obj.get("done"):
                        break
                    responses.append(obj)

            # Join all text parts from the stream
            output = "".join([o["response"] for o in responses])

            start = output.find("{")
            end = output.rfind("}") + 1
            data = output[start:end]


            # Parse the response format possibilities
            if isinstance(data, dict):
                if "text" in data:
                    return data["text"]
                if "results" in data:
                    return "".join(r.get("content", "") for r in data["results"])
                # fall back:
                return str(data)
            return str(data)
