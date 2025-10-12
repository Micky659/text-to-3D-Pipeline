import os
from pathlib import Path
import datetime
from .config import settings
from diffusers import StableDiffusionPipeline
import torch
from PIL import Image

def generate_texture_image(prompt: str, out_dir: Path, model_id: str = None, device: str = None, seed: int = None):
    model_id = model_id or settings.FAST_MODEL_ID
    device = device or settings.DEVICE
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"texture_{datetime.datetime.now().strftime('%m_%d__%H_%M_%S')}.png"

    if StableDiffusionPipeline is None:
        raise RuntimeError("diffusers or torch not available. Install diffusers[torch] and torch with CUDA support to use fast textures.")

    pipe = StableDiffusionPipeline.from_pretrained(model_id, torch_dtype=torch.float16)
    pipe.to(device)

    if seed is not None:
        generator = torch.Generator(device).manual_seed(int(seed))
        img = pipe(prompt, generator=generator).images[0]
    else:
        img = pipe(prompt).images[0]

    img.save(str(out_path))
    return out_path
