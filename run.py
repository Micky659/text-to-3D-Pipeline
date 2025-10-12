import argparse
from agents.orchestrator import Orchestrator
import json

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", type=str, help="Natural language scene request", required=True)
    parser.add_argument("--scene_id", type=str, default=None)
    parser.add_argument("--llm_mode", type=str, default="deepseek")
    parser.add_argument("--texture_mode", type=str, choices=["none", "gen_and_map", "diffusion"], default="gen_and_map",
                        help="Texture mode: none | gen_and_map (fast) | diffusion (TEXTurePaper)")
    parser.add_argument("--categories_json", type=str, default='static/categories_metadata.json')
    args = parser.parse_args()

    orchestrator = Orchestrator(llm_mode=args.llm_mode,
                                categories_path=args.categories_json,
                                texture_mode=args.texture_mode)

    resp = orchestrator.handle_request(args.text, scene_id=args.scene_id)
    print(f"Scene manifest saved at: {resp['manifest_path']}")

if __name__ == "__main__":
    main()

