import argparse
from agents.orchestrator import Orchestrator
from layout_module.config import settings
import json
import os

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", type=str, help="Natural language scene request", required=True)
    parser.add_argument("--scene_id", type=str, default=None)
    parser.add_argument("--llm_url", type=str, default=None)
    parser.add_argument("--llm_model", type=str, default=None)
    parser.add_argument("--categories_json", type=str, default=None)
    args = parser.parse_args()

    orchestrator = Orchestrator(llm_base_url=args.llm_url or settings.LLM_BASE_URL,
                                llm_model=args.llm_model or settings.LLM_MODEL,
                                categories_path=args.categories_json)

    resp = orchestrator.handle_request(args.text, scene_id=args.scene_id)
    print(json.dumps(resp, indent=2))

if __name__ == "__main__":
    main()
