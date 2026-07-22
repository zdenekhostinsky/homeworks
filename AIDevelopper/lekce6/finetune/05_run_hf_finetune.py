"""Step 5: launch the LoRA fine-tuning job on Hugging Face Jobs and wait for it to finish."""

import json
import sys
import time

from dotenv import load_dotenv
from huggingface_hub import HfApi, fetch_job_logs, get_token, inspect_job, run_uv_job

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from config import (
    BASE_DIR,
    HF_BASE_MODEL,
    HF_DATASET_REPO_SUFFIX,
    HF_JOB_FLAVOR,
    HF_JOB_INFO_FILE,
    HF_JOB_TIMEOUT,
    HF_MODEL_REPO_SUFFIX,
)

TRAIN_SCRIPT = BASE_DIR / "train_lora.py"


def load_job_info():
    if HF_JOB_INFO_FILE.exists():
        return json.loads(HF_JOB_INFO_FILE.read_text(encoding="utf-8"))
    return {}


def save_job_info(info):
    HF_JOB_INFO_FILE.write_text(json.dumps(info, indent=2), encoding="utf-8")


def main():
    load_dotenv()
    api = HfApi()
    username = api.whoami()["name"]
    dataset_repo = f"{username}/{HF_DATASET_REPO_SUFFIX}"
    model_repo = f"{username}/{HF_MODEL_REPO_SUFFIX}"

    job_info = load_job_info()

    if job_info.get("job_id") and job_info.get("stage") not in ("COMPLETED", "ERROR", "CANCELED"):
        print(f"[resume] Found existing job {job_info['job_id']}, watching it instead of starting a new one.")
        job_id = job_info["job_id"]
    else:
        print(f"[1/2] Starting HF Job: model={HF_BASE_MODEL}  flavor={HF_JOB_FLAVOR}  timeout={HF_JOB_TIMEOUT}")
        job = run_uv_job(
            str(TRAIN_SCRIPT),
            script_args=[
                "--base-model", HF_BASE_MODEL,
                "--dataset-repo", dataset_repo,
                "--model-repo", model_repo,
            ],
            image="huggingface/trl",
            flavor=HF_JOB_FLAVOR,
            timeout=HF_JOB_TIMEOUT,
            secrets={"HF_TOKEN": get_token()},
        )
        job_id = job.id
        job_info.update(
            {
                "job_id": job_id,
                "job_url": job.url,
                "dataset_repo": dataset_repo,
                "model_repo": model_repo,
                "base_model": HF_BASE_MODEL,
            }
        )
        save_job_info(job_info)
        print(f"      -> job created: {job.url}")

    print("[2/2] Streaming logs (this can take from minutes to ~1-2 hours)")
    seen_lines = 0
    while True:
        logs = list(fetch_job_logs(job_id=job_id))
        for line in logs[seen_lines:]:
            print(f"      {line}")
        seen_lines = len(logs)

        status = inspect_job(job_id=job_id).status
        if status.stage in ("COMPLETED", "ERROR", "CANCELED"):
            job_info["stage"] = status.stage
            job_info["message"] = status.message
            save_job_info(job_info)
            print(f"\nJob finished with stage={status.stage}")
            if status.stage != "COMPLETED":
                print(f"Message: {status.message}")
            else:
                print(f"Adapter + results.json pushed to https://huggingface.co/{model_repo}")
            break

        time.sleep(15)


if __name__ == "__main__":
    main()
