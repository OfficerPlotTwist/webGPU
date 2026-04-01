# Runpod Fresh Start

Use these commands on a fresh Runpod GPU box over SSH.

Replace `<YOUR-REPO-URL>` with your repo URL.

## 1. Clone the repo

```bash
cd /workspace
git clone https://github.com/OfficerPlotTwist/webGPU live-diffusion
cd /workspace/live-diffusion
```

## 2. Create and activate the virtualenv

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
```

## 3. Install the repo requirements

```bash
pip install -r requirements.txt
```

## 4. Install PyTorch with CUDA

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
```

## 5. Install the diffusers runtime

```bash
pip install diffusers transformers accelerate safetensors huggingface_hub
```

## 6. Log into Hugging Face

```bash
python -m pip install huggingface_hub
  hf auth login
```

Paste your token when prompted.

## 7. Pull the latest repo state

```bash
git pull
```

## 8. Start the server with the helper script

```bash
cd /workspace/live-diffusion
bash start_server.sh
```

Expected health result from a second terminal:

```bash
curl http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok","backend":"diffusers"}
```

## 9. Create the session from a second terminal

```bash
cd /workspace/live-diffusion
bash create_session.sh
```

## 10. If you update the repo later

```bash
cd /workspace/live-diffusion
git pull
source .venv/bin/activate
```

Then restart:

```bash
bash start_server.sh
```

And recreate the session:

```bash
bash create_session.sh
```
