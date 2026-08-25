"""Step 2: upload the training data and run the fine-tuning job on OpenAI."""

import json
import sys
import time

from dotenv import load_dotenv
from openai import OpenAI, PermissionDeniedError, BadRequestError

from config import BASE_MODEL, JOB_INFO_FILE, TRAIN_FILE, VALID_FILE

POLL_SECONDS = 20


def load_job_info():
    if JOB_INFO_FILE.exists():
        return json.loads(JOB_INFO_FILE.read_text(encoding="utf-8"))
    return {}


def save_job_info(info):
    JOB_INFO_FILE.write_text(json.dumps(info, indent=2), encoding="utf-8")


def upload_file(client, path, label):
    print(f"      uploading {label} ({path.name}) ...")
    with open(path, "rb") as f:
        uploaded = client.files.create(file=f, purpose="fine-tune")
    while True:
        info = client.files.retrieve(uploaded.id)
        if info.status == "processed":
            print(f"      -> {label} ready: {info.id}")
            return info.id
        if info.status == "error":
            raise RuntimeError(f"{label} upload failed: {info}")
        time.sleep(3)


def main():
    load_dotenv()
    client = OpenAI()

    job_info = load_job_info()

    if job_info.get("job_id") and not job_info.get("fine_tuned_model"):
        print(f"[resume] Found existing job {job_info['job_id']}, polling instead of creating a new one.")
        job_id = job_info["job_id"]
    else:
        print("[1/3] Uploading training and validation files")
        try:
            train_file_id = upload_file(client, TRAIN_FILE, "train file")
            valid_file_id = upload_file(client, VALID_FILE, "validation file")
        except (PermissionDeniedError, BadRequestError) as e:
            print("File upload failed. If the error mentions fine-tuning eligibility, your OpenAI")
            print("org may be blocked from creating fine-tuning jobs (OpenAI restricted new access")
            print("starting May 2026). Consider the Hugging Face + LoRA alternative instead.")
            print(f"Details: {e}")
            sys.exit(1)

        print("[2/3] Creating the fine-tuning job")
        try:
            job = client.fine_tuning.jobs.create(
                training_file=train_file_id,
                validation_file=valid_file_id,
                model=BASE_MODEL,
                suffix="ilp-docs",
            )
        except (PermissionDeniedError, BadRequestError) as e:
            print("Job creation was rejected. This is the expected symptom if your org does not")
            print("have fine-tuning access (OpenAI stopped granting it to new orgs on 2026-05-07).")
            print("Fallback: switch to the Hugging Face + PEFT/LoRA route on a small open model.")
            print(f"Details: {e}")
            sys.exit(1)

        job_id = job.id
        job_info.update(
            {
                "job_id": job_id,
                "train_file_id": train_file_id,
                "valid_file_id": valid_file_id,
                "base_model": BASE_MODEL,
            }
        )
        save_job_info(job_info)
        print(f"      -> job created: {job_id}")

    print("[3/3] Polling job status (this can take from minutes to a few hours)")
    seen_events = set()
    while True:
        job = client.fine_tuning.jobs.retrieve(job_id)

        events = client.fine_tuning.jobs.list_events(job_id, limit=20)
        for event in reversed(events.data):
            if event.id not in seen_events:
                seen_events.add(event.id)
                print(f"      [{event.created_at}] {event.message}")

        if job.status == "succeeded":
            job_info["fine_tuned_model"] = job.fine_tuned_model
            job_info["trained_tokens"] = job.trained_tokens
            save_job_info(job_info)
            print(f"\nDone. Fine-tuned model: {job.fine_tuned_model}")
            print(f"Trained tokens: {job.trained_tokens}")
            break

        if job.status in ("failed", "cancelled"):
            print(f"\nJob ended with status={job.status}")
            if job.error:
                print(f"Error: {job.error}")
            sys.exit(1)

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
