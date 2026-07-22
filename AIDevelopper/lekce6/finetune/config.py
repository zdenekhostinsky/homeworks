from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

SOURCE_DATASET = BASE_DIR.parent / "sources" / "result" / "ILPDocumentation_dataset.jsonl"

DATA_DIR = BASE_DIR / "data"
TRAIN_FILE = DATA_DIR / "train.jsonl"
VALID_FILE = DATA_DIR / "valid.jsonl"
EVAL_FILE = DATA_DIR / "eval.jsonl"

JOB_INFO_FILE = BASE_DIR / "finetune_job.json"

RESULTS_DIR = BASE_DIR / "results"
RESULTS_FILE = RESULTS_DIR / "comparison.xlsx"

# Fine-tunable snapshot of the cheapest current OpenAI model.
# NOTE: OpenAI blocked new fine-tuning jobs org-wide from 2026-05-07 (platform wind-down).
# Kept here only because JUDGE_MODEL below still uses plain (non-fine-tuning) chat inference.
BASE_MODEL = "gpt-4o-mini-2024-07-18"
JUDGE_MODEL = "gpt-4o-mini"

SYSTEM_PROMPT = (
    "You are a support assistant for the Internal Logistics Platform (ILP), "
    "the company's core logistics platform. Answer questions about the ILP "
    "accurately and concisely, based on its technical documentation."
)

RANDOM_SEED = 42
EVAL_SIZE = 20  # held-out questions used for the before/after benchmark
VALID_RATIO = 0.1  # share of the remaining pairs used as OpenAI validation set

# --- Hugging Face Jobs route (replaces the blocked OpenAI fine-tuning route) ---
HF_BASE_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
HF_DATASET_REPO_SUFFIX = "ala-docs-ft-data"
HF_MODEL_REPO_SUFFIX = "ala-docs-qwen2.5-1.5b-lora"
HF_JOB_FLAVOR = "t4-medium"  # $0.60/h, 1x T4 16GB - plenty for a 1.5B QLoRA job
HF_JOB_TIMEOUT = "2h"
HF_JOB_INFO_FILE = BASE_DIR / "hf_finetune_job.json"
HF_RESULTS_FILE = RESULTS_DIR / "comparison_hf.xlsx"
