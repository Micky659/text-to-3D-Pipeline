# 3D Scene Generation Pipeline - Setup and Usage Guide

## Project Overview

This project consists of two main components:
1. **Scene Generation Pipeline**: A transformer-based pipeline with two texturing methods for generating complete 3D scenes from text
2. **Mesh Transformer Training**: A modified MeshGPT model for training and generating 3D mesh assets

---

## Table of Contents

1. [Environment Setup](#environment-setup)
2. [Scene Generation Pipeline](#scene-generation-pipeline)
3. [Mesh Transformer Training](#mesh-transformer-training)
4. [Troubleshooting](#troubleshooting)

---

## Environment Setup

### Prerequisites

- **Operating System**: Windows 10/11, Linux (Ubuntu 20.04+), or macOS
- **Python Version**: 3.10
- **GPU**: NVIDIA GPU with CUDA support (minimum 8GB VRAM recommended, 16GB+ for training)
- **CUDA Version**: 11.8 or 12.1
- **Storage**: At least 500GB free space for mesh model training (checkpoints, models and datasets)

### Step 1: Create Python Environment

```bash
# Create a new conda environment (recommended)
conda create -n scene_gen python=3.10
conda activate scene_gen

# OR using venv
python3.10 -m venv scene_gen_env
# Windows
scene_gen_env\Scripts\activate
# Linux/macOS
source scene_gen_env/bin/activate
```

### Step 2: Install PyTorch with CUDA

```bash
# For CUDA 11.8
pip install torch==2.1.0 torchvision==0.16.0 torchaudio==2.1.0 --index-url https://download.pytorch.org/whl/cu118

# For CUDA 12.1
pip install torch==2.1.0 torchvision==0.16.0 torchaudio==2.1.0 --index-url https://download.pytorch.org/whl/cu121

# Verify installation
python -c "import torch; print(f'PyTorch: {torch.__version__}'); print(f'CUDA Available: {torch.cuda.is_available()}')"
```

### Step 3: Install Core Dependencies

```bash
pip install -r requirements.txt
```
### Step 4: Ollama Setup for Local LLM

Ollama provides local LLM inference for the scene generation pipeline.

#### Windows Installation:
1. Download Ollama from: https://ollama.ai/download/windows
2. Run the installer
3. Open Command Prompt and verify: `ollama --version`

#### Linux Installation:
```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

#### macOS Installation:
```bash
brew install ollama
```

#### Start Ollama Service:
```bash
# Windows: Ollama starts automatically as a service

# Linux/macOS: Start the service
ollama serve &
```

#### Pull Required Model:
```bash
# Download the recommended model (or any other compatible model)
ollama pull qwen3-coder:30b

# Verify the model is available
ollama list
```

### Step 5: DeepSeek API Setup (Alternative to Ollama)

If you prefer using DeepSeek's cloud API instead of local Ollama:

1. Sign up at https://platform.deepseek.com/
2. Generate an API key from your dashboard
3. Add the key to `layout_module/config.py`:

```python
DEEPSEEK_KEY: str = "your_api_key_here"
```

---

## Scene Generation Pipeline

The scene generation pipeline creates complete 3D scenes from natural language descriptions through layout planning, mesh generation, and texturing.

### Directory Structure

```
project_root/
├── agents/
│   ├── orchestrator.py
│   ├── input_interpreter_agent.py
│   ├── layout_planner_agent.py
│   └── scene_editor_agent.py
├── layout_module/
│   ├── config.py
│   ├── llm_client.py
│   ├── models.py
│   └── utils.py
├── mesh_generator/
│   └── generator.py
├── texture_module/
│   ├── config.py
│   ├── generate_textured_assets.py
│   └── external_texture.py
├── static/
│   └── categories_metadata.json
├── output/
├── run.py
└── requirements.txt
```

### Configuration

#### 1. Configure Layout Module

Edit `layout_module/config.py`:

```python
class Settings(BaseSettings):
    # Ollama settings (for local LLM)
    LLM_BASE_URL_OLLAMA: str = "http://localhost:11434/api/generate"
    LLM_MODEL: str = "qwen3-coder:30b"  # Change to your pulled model
    
    # DeepSeek settings (for cloud API)
    LLM_BASE_URL_DEEPSEEK: str = "https://api.deepseek.com"
    DEEPSEEK_KEY: str = "your_api_key_here"
    
    # Output directory
    OUTPUT_DIR: Path = Path("./output")
    
    # Spatial constraints
    DEFAULT_CLEARANCE: float = 0.4  # meters
    DEFAULT_WALL_CLEARANCE: float = 0.15
```

#### 2. Configure Texture Module

Edit `texture_module/config.py`:

```python
class TextureSettings(BaseSettings):
    OUTPUT_DIR: Path = Path("./textured_assets")
    FAST_MODEL_ID: str = "dream-textures/texture-diffusion"
    DEVICE: str = "cuda"  # or "cpu" if no GPU
    
    # TEXTurePaper settings (only needed for diffusion mode)
    TEXTUREPAPER_RUN_CMD: str = "path/to/TEXTurePaper/.venv/Scripts/python.exe"
    TEXTUREPAPER_EXPERIMENTS_DIR: Path = Path("path/to/TEXTurePaper/experiments")
    WORKDIR: str = "path/to/TEXTurePaper"
    CFG_DIR: str = "path/to/TEXTurePaper/configs/text_guided"
```

### TEXTurePaper Setup

TEXTurePaper provides high-quality diffusion-based texturing. This is optional; the pipeline works with `gen_and_map` mode without it.

#### 1. Clone TEXTurePaper Repository:
```bash
cd /path/to/your/projects
git clone https://github.com/TEXTurePaper/TEXTurePaper.git
cd TEXTurePaper
```

#### 2. Create Separate Environment for TEXTurePaper:
```bash
# Create new environment for TEXTurePaper
conda create -n texturepaper python=3.9
conda activate texturepaper

# Install dependencies
pip install torch==1.13.1 torchvision==0.14.1 --index-url https://download.pytorch.org/whl/cu117
pip install -r requirements.txt
```

#### 3. Download TEXTurePaper Models:
```bash
# Follow TEXTurePaper's instructions to download pretrained models
# Usually involves downloading checkpoint files to a 'checkpoints' directory
```

#### 4. Update Texture Config:
Update paths in `texture_module/config.py` to point to your TEXTurePaper installation.

### Running Scene Generation

#### Basic Usage:

```bash
# Generate a scene with default settings (Ollama + fast texturing)
python run.py --text "a cozy living room with a sofa, coffee table, and bookshelf"

# Using DeepSeek API instead of Ollama
python run.py --text "a modern office workspace" --llm_mode deepseek

# With diffusion-based texturing (requires TEXTurePaper setup)
python run.py --text "a kitchen with appliances" --texture_mode diffusion
```

#### Advanced Options:

```bash
# Full command with all options
python run.py \
    --text "a Victorian dining room with ornate furniture" \
    --scene_id my_scene_001 \
    --llm_mode ollama \
    --ollama_model llama3.2:latest \
    --texture_mode gen_and_map \
    --categories_json static/categories_metadata.json
```

#### Editing Existing Scenes:

```bash
# Edit a previously generated scene
python run.py \
    --text "make the sofa red and change the floor lamp" \
    --scene_id scene_abc123 \
    --llm_mode ollama \
    --texture_mode gen_and_map
```

### Pipeline Parameters

- `--text`: Natural language description of the scene (required)
- `--scene_id`: Unique identifier for the scene (auto-generated if not provided)
- `--llm_mode`: Choose LLM backend: `ollama` (local) or `deepseek` (cloud API)
- `--ollama_model`: Specific Ollama model to use (default from config)
- `--texture_mode`: Texturing method:
  - `gen_and_map`: Fast texture generation and mapping (recommended)
  - `diffusion`: High-quality diffusion-based texturing (requires TEXTurePaper)
- `--categories_json`: Path to object category metadata file

### Output

The pipeline generates a scene manifest JSON file in the output directory:

```
output/
└── scene_abc123_scene_manifest.json
```

The manifest contains:
- Room dimensions
- Object placements (position, rotation, scale)
- Asset paths (mesh and texture files)
- Texture information
- Metadata and provenance tracking

### Pipeline Workflow

1. **Input Interpretation**: Parses natural language to extract objects, relationships, and style
2. **Layout Planning**: Uses LLM to arrange objects in 3D space with verification
3. **Mesh Generation**: Generates 3D mesh assets for each object category
4. **Texturing**: Applies textures based on style and object type
5. **Manifest Export**: Saves complete scene description to JSON

---

## Mesh Transformer Training

The mesh transformer is a neural network that learns to generate 3D meshes from text descriptions. It consists of two stages: autoencoder training and transformer training.

### Directory Structure

```
project_root/
├── Data/
│   └── meshData_org.npz
├── Models/
│   ├── mesh-encoder.pt
│   └── mesh-transformer.pt
├── checkpoints/
├── data_scripts/
│   ├── Mesh_dataset.py
│   └── helper_funcs.py
├── model_scripts/
│   ├── autoencoder.py
│   └── transformer.py
├── training_scripts/
│   ├── autoencoder_trainer.py
│   └── transformer_trainer.py
├── encoder_training_main.py
├── transformer_training_main.py
└── mesh_generation.py
```

### Data Preparation

The training pipeline expects datasets in NumPy `.npz` format with the following structure:

```python
{
    'faces': np.array,      # Triangle faces
    'vertices': np.array,   # Vertex positions
    'texts': str,          # Category label or text description
}
```

Processed dataset is available in the `Data/` directory:
- `meshData_org.npz`: MeshGPT-provided dataset after normalization and preprocessing

### Stage 1: Autoencoder Training

The autoencoder learns to compress and reconstruct 3D meshes into a discrete latent space.

#### Configuration

Edit `encoder_training_main.py` to adjust hyperparameters:

#### Training from Scratch

```bash
# Activate environment
conda activate scene_gen

# Start training
python encoder_training_main.py
```

### Stage 2: Transformer Training

The transformer learns to generate mesh token sequences conditioned on text descriptions.

#### Configuration

Edit `transformer_training_main.py`:

#### Training from Scratch

```bash
# Activate environment
conda activate scene_gen

# Preprocess dataset (embed texts and generate codes)
# This is done automatically in the script

# Start training
python transformer_training_main.py
```

### Run Inference

```bash
python mesh_generation.py
```

---

## Scene and Asset Visualization

After generating scenes or training mesh models, you can visualize the results using the included web-based viewers.

### Scene Visualization Web Server

The scene visualizer allows you to view complete 3D scenes from manifest JSON files in multiple views (2D layout, 3D boxes, and full 3D assets with textures).

#### Setup and Launch


**Step 1: Start the Server**

```bash
# Activate your environment
conda activate scene_gen

# Navigate to the scene_assembly directory
cd scene_assembly

# Start the server
python scene_assembly_web.py
```

The server will start on `http://localhost:8000`

**Step 2: Open in Browser**

Open your web browser and navigate to:
```
http://localhost:8000
```

#### Using the Scene Visualizer

**Loading Scenes:**
1. Select a scene from the dropdown menu (automatically populated from your output directory)
2. Click "Load Scene" to visualize
3. Or enter a custom path to a manifest JSON file and click "Load Custom"

**Viewing Modes:**
- **📐 2D Layout**: Top-down view showing object positions and room boundaries
- **📦 3D Boxes**: 3D view with objects represented as colored boxes
- **🎨 3D Assets**: Full 3D view with textured meshes (if assets are loaded)

**Controls:**
- **Left Click + Drag**: Rotate the 3D view
- **Scroll Wheel**: Zoom in/out
- **🔄 Rotate View**: Cycle through preset isometric camera angles
- **💾 Save Layout**: Export the current view as a PNG image

**Features:**
- Real-time 3D rendering using Three.js
- Automatic loading of OBJ meshes and textures
- Room boundaries and grid visualization
- Scene information panel showing dimensions and object count

### Single Asset Viewer

For viewing individual 3D mesh assets (OBJ files with optional MTL and textures).

#### Launch the Asset Viewer

```bash
cd scene_assembly

# Start a simple HTTP server
python -m http.server 8080
```

Open in browser:
```
http://localhost:8080/asset_viewer.html
```

#### Using the Asset Viewer

**Loading Assets:**

**Method 1 - Drag and Drop:**
1. Drag and drop OBJ, MTL, and texture files into the drop zone
2. Files are automatically categorized by extension
3. Model loads instantly with all materials applied

**Method 2 - File Selection:**
1. Click "Choose OBJ File" and select your .obj file
2. Optionally select MTL file for material definitions
3. Optionally select texture/PNG file for surface textures
4. Model loads after selecting OBJ file

**Features:**
- Interactive 3D rotation (drag with mouse)
- Zoom with scroll wheel
- Automatic camera positioning based on model bounds
- High-resolution screenshot capture
- Automatic cropping to model bounds with padding
- Support for textured and untextured models

**Controls:**
- **Mouse Drag**: Rotate the model
- **Scroll Wheel**: Zoom in/out
- **🔄 Reset View**: Return to default camera position
- **📸 Capture Image**: Save PNG

**Supported Formats:**
- **OBJ files**: 3D mesh geometry (required)
- **MTL files**: Material definitions (optional)
- **Texture files**: PNG, JPG, JPEG (optional)

---

## Troubleshooting

### Common Issues

#### 1. CUDA Out of Memory

**Symptoms**: `RuntimeError: CUDA out of memory`

**Solutions**:
- Reduce batch size
- Increase gradient accumulation steps
- Clear cache: `torch.cuda.empty_cache()`

#### 2. Ollama Connection Error

**Symptoms**: `Connection refused` or `requests.exceptions.ConnectionError`

**Solutions**:
- Verify Ollama is running: `ollama list`
- Check port 11434 is not blocked

#### 3. TEXTurePaper Subprocess Failures

**Symptoms**: `RuntimeError: TEXTurePaper run failed`

**Solutions**:
- Verify TEXTurePaper environment is set up correctly
- Check paths in `texture_module/config.py`
- Ensure PYTHONPATH is set correctly
- Run TEXTurePaper standalone first to verify installation

#### 4. Troubleshooting Visualization

**Symptoms**: Assets not displayed when loading scene manifests

**Solutions**:
- If assets don't load, check the browser console (F12) for errors
- Verify file paths in the manifest JSON are correct
- Ensure the server has read permissions for the output directory
- For missing textures, check MTL file references match actual filenames

### Getting Help

If you encounter issues:

1. Verify environment setup (Python version, CUDA, dependencies)
2. Ensure dataset and model paths are correct
3. Check GPU memory usage: `nvidia-smi`
4. Review configuration files for typos
5. Test components individually

---

## Quick Start Summary

```bash
# 1. Setup environment
conda create -n scene_gen python=3.10
conda activate scene_gen

# 2. Install dependencies
pip install -r requirements.txt

# 3. Setup Ollama
ollama pull qwen3-coder:30b

# 4. Configure paths in config files
# Edit layout_module/config.py and texture_module/config.py

# 5. Run scene generation
python run.py --text "a cozy living room" --llm_mode ollama --texture_mode gen_and_map

```

---

```bibtex
@mastersthesis{akshat2025textto3d,
  title     = {Text-to-3D Scene Generation: A Transformer-Driven Framework for Custom Virtual Environments},
  school    = {Brandenburgische Technische Universität Cottbus-Senftenberg},
  author    = {Kothari, Akshat},
  year      = {2025},
}
```
---

**End of Setup Guide**
