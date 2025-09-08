import requests
from typing import Dict, Any
import json
from .config import settings

class LLMClient:
    """
    Simple wrapper for Ollama-like HTTP generate endpoints.
    The endpoint path is configurable via settings.LLM_BASE_URL.
    Body shape depends on your server; this function uses a conservative
    shape but is easy to customize if your Ollama version differs.
    """

    def __init__(self, base_url: str = None, model: str = None):
        self.base_url = base_url or settings.LLM_BASE_URL
        self.model = model or settings.LLM_MODEL

    def generate(self, prompt: str, max_tokens: int = 1024, temperature: float = 0) -> str:
        body = {
            "model": self.model,
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
            # If Ollama endpoint expects different names, edit here.
        }
        resp = requests.post(self.base_url, json=body, timeout=120)
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

        print(data)


        # The response format possibilities:
        # 1) {"text": "..." } or 2) {"results": [{"content": "..."}]} etc.
        if isinstance(data, dict):
            if "text" in data:
                return data["text"]
            if "results" in data:
                # Example: results -> [{ "content": "..." }]
                return "".join(r.get("content", "") for r in data["results"])
            # fall back:
            return str(data)
        return str(data)
