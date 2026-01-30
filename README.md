# Spark-voice

**Spark** is a voice agent with personality: warm, quick-witted, and conversational. It runs locally using Pipecat: Silero VAD, smart-turn (LocalSmartTurnAnalyzerV3), Whisper STT (CPU), LM Studio (Gemma 3 1B or any OpenAI-compatible model), and **Kokoro** (default), Piper, or XTTS for TTS. CLI mode uses the system microphone and speaker; WebRTC serves the browser client by default.

## Requirements

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip + venv
- LM Studio running on port 3000 with a model loaded (e.g. `google_gemma-3-1b-it`)
- **TTS**: Default is **Kokoro** (in-process, no server). Optional: [Piper](https://github.com/rhasspy/piper) or [XTTS](https://github.com/coqui-ai/xtts-streaming-server) server; set `TTS=piper` or `TTS=xtts` and the corresponding URL in `.env`.
- On Linux: for local audio (PyAudio), install `portaudio19-dev` and a C compiler: `sudo apt install portaudio19-dev build-essential`. Use `CC=gcc uv sync` if the build picks clang and fails.
- For Kokoro TTS on Linux you may need: `sudo apt install espeak-ng`

For AMD RX 6600 (gfx1050) with ROCm, set before running:

```bash
export HSA_OVERRIDE_GFX_VERSION=10.3.0
```

<details>
<summary><strong>System and ROCm check</strong></summary>

Run the system check script to print CPU, RAM, GPU, and ROCm status:

```bash
./scripts/check_system.sh
```

This runs `rocm-smi` (and optionally `rocminfo`). Ensure ROCm is installed and the GPU is visible when using GPU workloads.

<details>
<summary><strong>If ROCm is not installed (HX99G)</strong></summary>

The following steps target **Minisforum HX99G** (and similar AMD systems). If your system already has ROCm, skip to [Setup](#setup).

**Install essentials and a supported kernel**

```bash
sudo apt update && sudo apt upgrade
sudo apt-get install neofetch htop wget curl
sudo apt install linux-image-generic
sudo add-apt-repository ppa:danielrichter2007/grub-customizer
sudo apt install grub-customizer
```

- Launch **Grub Customizer** → **General** tab → set default entry to **Advanced options for Ubuntu** → **Ubuntu, with Linux x.x.x-x-generic** → Save → `sudo reboot`
- Boot into that kernel, then install headers:

```bash
sudo apt install "linux-headers-$(uname -r)" "linux-modules-extra-$(uname -r)"
```

**Add users to render/video groups**

```bash
sudo usermod -a -G render,video $LOGNAME
echo 'ADD_EXTRA_GROUPS=1' | sudo tee -a /etc/adduser.conf
echo 'EXTRA_GROUPS=video' | sudo tee -a /etc/adduser.conf
echo 'EXTRA_GROUPS=render' | sudo tee -a /etc/adduser.conf
```

**Install AMDGPU and ROCm**

```bash
sudo apt update
wget https://repo.radeon.com/amdgpu-install/6.1.3/ubuntu/focal/amdgpu-install_6.1.60103-1_all.deb
sudo apt install ./amdgpu-install_6.1.60103-1_all.deb
sudo amdgpu-install --no-dkms --usecase=hiplibsdk,rocm
sudo rocminfo
sudo reboot
```

**Environment (if you hit unsupported-GPU errors)**

Set as needed for your GPU (example for older GFX):

```bash
export HSA_OVERRIDE_GFX_VERSION=10.3.0
```

**Uninstall (if needed)**

```bash
amdgpu-install --uninstall
```

Full gist: [AMD ROCm installation (HX99G)](https://gist.github.com/furaar/ee05a5ef673302a8e653863b6eaedc90).

</details>

</details>

## Setup

1. Copy env example and edit:

   ```bash
   cp .env.example .env
   ```

   Set in `.env`:

   - `HF_TOKEN` – Hugging Face token (already set if you have one)
   - `LM_STUDIO_BASE_URL` – default `http://localhost:3000/v1`
   - `OPENAI_API_KEY` – any non-empty value for LM Studio (e.g. `lm-studio`)
   - `LM_MODEL` – exact model id as shown in LM Studio (e.g. `google_gemma-3-1b-it`)
   - **TTS**: `TTS=kokoro` (default), `TTS=piper`, or `TTS=xtts`. For Kokoro: `KOKORO_VOICE=af_heart`, `KOKORO_LANG=a`. For Piper/XTTS set `PIPER_BASE_URL` or `XTTS_BASE_URL`.

2. Install dependencies:

   ```bash
   uv sync
   ```

   Or with pip:

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # or .venv\Scripts\activate on Windows
   pip install -e .
   ```

3. Start LM Studio and run the server on port 3000 (e.g. in LM Studio: start the server and set port to 3000, or `lms server start --port 3000` if using the CLI). Load the model you set as `LM_MODEL`.

4. TTS:
   - **Kokoro** (default): No server. Set `TTS=kokoro`, `KOKORO_VOICE=af_heart`, `KOKORO_LANG=a`, optional `KOKORO_SPEED=1.0` (0.5–2.0). Voices: [Kokoro VOICES.md](https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md) (e.g. af_heart, af_bella, am_adam; bf_emma for British). **Voice emotes**: the LLM can start a phrase with `(excited)`, `(calm)`, `(whisper)`, `(sad)`, `(warm)`, etc.; these are stripped and only affect speech speed.
   - **Piper** or **XTTS**: Start the server and set `TTS=piper` or `TTS=xtts` and `PIPER_BASE_URL` or `XTTS_BASE_URL` in `.env`.

## Run

**Web client (default)** – `python bot.py` with no args starts WebRTC; open http://localhost:7860/client:

```bash
uv run python bot.py
```

Or explicitly:

```bash
uv run python bot.py -t webrtc
```

Install the web transport with `uv sync --extra webrtc` if needed.

**CLI (local mic and speaker):**

```bash
uv run python bot.py --local
```

**Daily (production-style):**

```bash
uv run python bot.py -t daily
```

Requires `DAILY_API_KEY` and `pipecat-ai[daily]`. See [UPGRADE.md](UPGRADE.md) for moving to GUI/web.

**Docker** – WebRTC by default; client at http://localhost:7860/client:

```bash
docker build -t spark-voice .
docker run -p 7860:7860 -e LM_STUDIO_BASE_URL=http://host.docker.internal:3000/v1 -e OPENAI_API_KEY=lm-studio -e LM_MODEL=google_gemma-3-1b-it spark-voice
```

Ensure LM Studio is running on the host (port 3000). Use `--add-host=host.docker.internal:host-gateway` on Linux if `host.docker.internal` is not available.

**Docker Compose** – Same as above with GPU passthrough and ports 7860 exposed; uses `.env` and `host.docker.internal` for LM Studio:

```bash
docker compose up -d --build
```

Then open http://localhost:7860/client. The Compose file passes through the GPU via AMD ROCm device passthrough (`/dev/kfd`, `/dev/dri`). For CPU-only, comment out the `devices` section in `docker-compose.yml`. The image runs the runner with `--host 0.0.0.0` so the connection is reachable from the host. For AMD GPUs (e.g. RX 6600), set `HSA_OVERRIDE_GFX_VERSION=10.3.0` in `.env` so ROCm can use the device. Whisper uses the GPU when PyTorch sees a CUDA/ROCm device; for full GPU on AMD you may need a ROCm-built PyTorch image.

## Pipeline

- **Input**: LocalAudioTransport (CLI) or WebRTC/Daily (web).
- **VAD / turn**: Silero VAD + LocalSmartTurnAnalyzerV3 (smart-turn-v3).
- **STT**: Whisper (Faster Whisper); GPU when available (CUDA/ROCm), else CPU.
- **LLM**: LM Studio via OpenAI-compatible API.
- **TTS**: Kokoro (in-process), or Piper/XTTS (HTTP server).
- **Output**: Same transport (speaker or browser).

## What you see when you run it

When you run `uv run python bot.py --local`:

1. **Pipecat banner** – Framework version and Python.
2. **Smart Turn / Silero** – "Loading ... Loaded" for local turn and VAD models.
3. **ALSA messages** – Lines like `pcm_dmix.c: unable to open slave`, `Unknown PCM cards.pcm.rear`, etc. These are normal on Linux when ALSA probes devices; the app usually still works with the default device.
4. **Whisper** – "Loading Whisper model... Loaded Whisper model" (first run may download the model).
5. **Pipeline linking** – "Linking ... -> ..." for each component (LocalAudio, Whisper, LLM, KokoroTTSService, etc.).
6. **Kokoro** – On first run you may see "Defaulting repo_id to hexgrad/Kokoro-82M" and a download of `kokoro-v1_0.pth` (~327MB). After that it’s cached.
7. **LM Studio** – "Generating chat from universal context" and TTFB; then Kokoro generates TTS from the LLM reply and plays it.

If the LLM tells a long story instead of a short hello, the model in LM Studio is ignoring the instruction; try a different model or a stricter system prompt. The "No module named pip" at the end is from a dependency (e.g. Kokoro) and is harmless when using `uv`.

## Troubleshooting

- **Whisper model not available**: Ensure `requests` is installed (included in deps) so the model can download from Hugging Face. First run may take a minute to download the Whisper model.
- **No TTS**: Default is Kokoro (no server). For Piper/XTTS set `TTS=piper` or `TTS=xtts` and the corresponding URL.
- **LM Studio**: Ensure the server is started on port 3000 and the model is loaded; `LM_MODEL` must match the model id in LM Studio.
- **ROCm**: Run `./scripts/check_system.sh` and set `HSA_OVERRIDE_GFX_VERSION=10.3.0` for RX 6600.
- **Portaudio**: On Linux install `portaudio19-dev` for local audio. Use `CC=gcc uv sync` if pyaudio build fails.
