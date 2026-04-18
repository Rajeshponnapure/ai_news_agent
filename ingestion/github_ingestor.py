import logging
from datetime import datetime, timezone
from typing import Generator

import httpx

from config.settings import settings

logger = logging.getLogger(__name__)

# GitHub repos to monitor for AI model/tool releases
GITHUB_REPOS = {
    # ── Major AI Companies ──
    "OpenAI": ["openai/openai-python", "openai/tiktoken", "openai/whisper"],
    "Anthropic": ["anthropics/anthropic-sdk-python", "anthropics/claude-code"],
    "Google": ["google/generative-ai-python", "google-deepmind/gemma", "google-deepmind/alphafold"],
    "Meta": ["facebookresearch/llama", "facebookresearch/fairseq", "facebookresearch/segment-anything"],
    "Mistral": ["mistralai/mistral-src", "mistralai/client-python"],
    "Hugging Face": ["huggingface/transformers", "huggingface/diffusers", "huggingface/peft", "huggingface/trl"],
    "Stability AI": ["stability-ai/generative-models", "stability-ai/stablediffusion3.5"],
    # ── AI Chips & Infrastructure ──
    "Nvidia": ["NVIDIA/TensorRT", "NVIDIA/NeMo", "NVIDIA/cuda-python", "NVIDIA/triton-inference-server"],
    "Intel": ["intel/intel-extension-for-pytorch", "intel/neural-compressor"],
    "AMD": ["ROCm/ROCm"],
    # ── AI Frameworks & Tools ──
    "LangChain": ["langchain-ai/langchain", "langchain-ai/langgraph"],
    "LlamaIndex": ["run-llama/llama_index"],
    "Weights & Biases": ["wandb/wandb"],
    "AnyScale": ["ray-project/ray"],
    "vLLM": ["vllm-project/vllm"],
    "Ollama": ["ollama/ollama"],
    "LM Studio": ["lmstudio-ai"],
    # ── AI Startups ──
    "Cohere": ["cohere-ai/cohere-python-sdk"],
    "Perplexity": ["perplexity-ai"],
    "Together AI": ["togethercomputer/OpenChatKit"],
    "Replicate": ["replicate/replicate-python"],
    "Sakana AI": ["SakanaAI"],
    # ── AI Coding ──
    "Cursor": ["getcursor/cursor"],
    "Tabnine": ["Tabnine"],
    "Continue": ["continuedev/continue"],
    # ── AI Research ──
    "DeepSeek": ["deepseek-ai/DeepSeek-V2", "deepseek-ai/DeepSeek-Coder"],
    "01.AI": ["01-ai/Yi"],
    "Qwen": ["QwenLM/Qwen"],
    "xAI": ["xai-org"],
}

AI_KEYWORDS = [
    "release", "v0", "v1", "v2", "v3", "v4", "model", "checkpoint",
    "weights", "finetune", "fine-tune", "alignment", "safety",
    "gpt", "claude", "gemini", "llama", "mistral", "diffusion",
    "transformer", "multimodal", "reasoning", "agent",
    "inference", "training", "gpu", "cuda", "tensorrt",
    "rag", "embedding", "chatbot", "llm", "language model",
    "deepseek", "yi", "qwen", "gemma", "alphafold",
]


class GitHubIngestor:
    def __init__(self):
        headers = {"Accept": "application/vnd.github+json"}
        if settings.GITHUB_TOKEN:
            headers["Authorization"] = f"Bearer {settings.GITHUB_TOKEN}"
        self.client = httpx.Client(timeout=30.0, headers=headers, follow_redirects=True)

    def _fetch_releases(self, repo: str) -> list[dict]:
        url = f"https://api.github.com/repos/{repo}/releases"
        try:
            resp = self.client.get(url, params={"per_page": 5})
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning("GitHub releases fetch failed for %s: %s", repo, e)
            return []

    def _is_relevant(self, tag: str, name: str, body: str) -> bool:
        text = f"{tag} {name} {body}".lower()
        return any(kw in text for kw in AI_KEYWORDS)

    def _extract_releases(self, company: str, repo: str) -> Generator[dict, None, None]:
        releases = self._fetch_releases(repo)
        for rel in releases:
            tag = rel.get("tag_name", "")
            name = rel.get("name", "") or tag
            body = rel.get("body", "") or ""
            if not self._is_relevant(tag, name, body):
                continue

            published = rel.get("published_at", "")
            html_url = rel.get("html_url", "")

            summary = body[:500] if body else f"Release {tag} for {repo}"

            yield {
                "title": f"{repo}: {name}"[:300],
                "company": company,
                "summary": summary,
                "timestamp": published or datetime.now(timezone.utc).isoformat(),
                "source_url": html_url,
                "source_name": "github",
            }

    def ingest(self) -> list[dict]:
        results = []
        for company, repos in GITHUB_REPOS.items():
            for repo in repos:
                logger.info("Ingesting GitHub releases for %s/%s", company, repo)
                entries = list(self._extract_releases(company, repo))
                logger.info("  → %d relevant releases from %s", len(entries), repo)
                results.extend(entries)
        return results

    def close(self):
        self.client.close()
