"""vLLM model server on Modal — an OpenAI-compatible endpoint for experiments Nebius can't serve.

You don't run this directly. `poseidon_compute.hosted_model` runs it ephemerally around an experiment (boots a
model, wires the endpoint into `llm_config`, tears it down):

    poseidon-host --model Qwen/Qwen2.5-7B-Instruct --gpu A10G -- <your experiment command>

SETUP (one-time): `pip install modal && modal setup` (browser auth). Gated models (e.g. Llama) need a
HF token: `modal secret create huggingface HF_TOKEN=hf_...`. Pick a GPU that fits the model: A10G (24GB)
~ up to 8B · A100-40GB ~ up to 32B · H100 for 70B (pass `--gpu` to hosted_model).

Advanced: `modal deploy poseidon_compute.modal_serve` gives a persistent shared endpoint; most teams won't need
it (the ephemeral hosted_model flow is simpler and leaves nothing running). Scaffolding ahead of live
credits — validate once your Modal account is funded.
"""
import os
import subprocess

import modal

# ---- config (override via env at deploy time) ----------------------------------------------------
MODEL = os.environ.get("MODAL_SERVE_MODEL", "Qwen/Qwen2.5-7B-Instruct")  # open by default (no HF gate)
GPU = os.environ.get("MODAL_SERVE_GPU", "A10G")
VLLM_PORT = 8000

app = modal.App("hackathon-serve")

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("vllm==0.6.6", "huggingface_hub[hf_transfer]==0.26.2")
    # [sprint fix] The settings above are read from the LOCAL environment, but the server code is
    # imported again inside the container, where those variables did not exist, so the container
    # always fell back to the default model (Qwen) whatever --model asked for. Bake them into the
    # image environment so the container sees the same values.
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1",
          "MODAL_SERVE_MODEL": MODEL,
          "MODAL_SERVE_GPU": GPU,
          "MODAL_SERVE_MAX_LEN": os.environ.get("MODAL_SERVE_MAX_LEN", "8192"),
          "MODAL_SERVE_MAX_INPUTS": os.environ.get("MODAL_SERVE_MAX_INPUTS", "64")})
)

# HF token (for gated models) + optional endpoint API key. Both secrets are optional: if you haven't
# created them, drop the corresponding entry.
# [sprint edit] Secrets are now opt-in. In current Modal versions `Secret.from_name` is lazy, so a
# missing secret is not caught here: it makes the whole app fail at startup. Ungated models (e.g.
# Qwen2.5-7B-Instruct) need no secret. For a gated model: MODAL_SERVE_SECRETS=huggingface
_secrets = [modal.Secret.from_name(n.strip())
            for n in os.environ.get("MODAL_SERVE_SECRETS", "").split(",") if n.strip()]


# [sprint edit, Apart collusion sprint] Cap the bill: never more than ONE GPU container, and let
# that one container take many requests at once (vLLM batches them), so parallel games do not
# each spin up their own GPU. Works on both older and newer Modal versions.
import inspect as _inspect
_fn_kwargs = dict(image=image, gpu=GPU, timeout=24 * 3600, scaledown_window=300, secrets=_secrets)
_params = _inspect.signature(app.function).parameters
if "max_containers" in _params:
    _fn_kwargs["max_containers"] = 1
elif "concurrency_limit" in _params:
    _fn_kwargs["concurrency_limit"] = 1
_MAX_INPUTS = int(os.environ.get("MODAL_SERVE_MAX_INPUTS", "64"))


def _concurrent(f):
    if hasattr(modal, "concurrent"):
        return modal.concurrent(max_inputs=_MAX_INPUTS)(f)
    return f


@app.function(**_fn_kwargs)
@_concurrent
@modal.web_server(port=VLLM_PORT, startup_timeout=900)
def serve():
    """Launch vLLM's OpenAI-compatible server; Modal proxies it to a public URL."""
    cmd = [
        "python", "-m", "vllm.entrypoints.openai.api_server",
        "--model", MODEL,
        "--host", "0.0.0.0",
        "--port", str(VLLM_PORT),
        "--served-model-name", MODEL,
        # [sprint edit] a shorter context fits a 7-8B model plus its cache on a 24 GB A10G
        "--max-model-len", os.environ.get("MODAL_SERVE_MAX_LEN", "8192"),
    ]
    api_key = os.environ.get("MODAL_SERVE_API_KEY")
    if api_key:
        cmd += ["--api-key", api_key]   # clients must send this as their key
    subprocess.Popen(" ".join(cmd), shell=True)
