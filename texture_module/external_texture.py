import os, subprocess, time, yaml
from pathlib import Path
from .config import settings

def write_texturepaper_yaml(exp_name: str, shape_path: str, text_template: str, seed: int = 42, out_dir: str = None):
    cfg = {
        "log": {"exp_name": exp_name},
        "guide": {"text": text_template, "append_direction": True, "shape_path": shape_path},
        "optim": {"seed": int(seed)}
    }
    cfg_dir = Path(out_dir) if out_dir else Path(settings.CFG_DIR)
    cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = cfg_dir / f"{exp_name}.yaml"
    with open(cfg_path, "w") as f:
        yaml.safe_dump(cfg, f)
    return cfg_path

def run_texturepaper_with_config(cfg_path: str):
    cfg_path = Path(cfg_path)
    exp_name = cfg_path.stem
    workdir = settings.WORKDIR
    env = os.environ.copy()
    env["PYTHONPATH"] = workdir  # so Python can find `src`

    # Run command: python -m scripts.run_texture --config_path=configs/text_guided/bench.yaml
    cmd = settings.TEXTUREPAPER_RUN_CMD.split("-") + ["--config_path", str(cfg_path)]
    # run in shellless mode
    # proc = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True, env=env)
    #
    # if proc.returncode != 0:
    #     raise RuntimeError(f"TEXTurePaper run failed: {proc.returncode}\nstderr:\n{proc.stderr}\nstdout:\n{proc.stdout}")


    proc = subprocess.Popen(cmd, cwd=workdir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out_bytes, err_bytes = proc.communicate()

    out = out_bytes.decode("utf-8", errors="replace") if isinstance(out_bytes, (bytes, bytearray)) else str(out_bytes)
    err = err_bytes.decode("utf-8", errors="replace") if isinstance(err_bytes, (bytes, bytearray)) else str(err_bytes)

    if proc.returncode != 0:
        raise RuntimeError(f"subprocess failed rc={proc.returncode}\nstdout:\n{out}\nstderr:\n{err}")


    exp_mesh_dir = settings.TEXTUREPAPER_EXPERIMENTS_DIR / exp_name / "mesh"
    if not exp_mesh_dir.exists():
        # try to find mesh obj, mtl, and texture files
        possible = list(settings.TEXTUREPAPER_EXPERIMENTS_DIR.glob(f"**/{exp_name}/mesh"))
        if possible:
            exp_mesh_dir = possible[0]
        else:
            raise FileNotFoundError(f"Could not find generated experiment mesh folder for {exp_name} under {settings.TEXTUREPAPER_EXPERIMENTS_DIR}")
    mesh_path = exp_mesh_dir / "mesh.obj"
    albedo = exp_mesh_dir / "albedo.png"
    mtl = exp_mesh_dir / "mesh.mtl"
    if not mesh_path.exists():
        raise FileNotFoundError(f"mesh.obj not found at {mesh_path}")
    return {"mesh_obj": str(mesh_path), "albedo": str(albedo) if albedo.exists() else None, "mtl": str(mtl) if mtl.exists() else None}
