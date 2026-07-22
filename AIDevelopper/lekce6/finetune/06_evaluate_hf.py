"""Step 6: judge the HF Job's before/after answers and write the benchmark Excel."""

import json

from dotenv import load_dotenv
from huggingface_hub import hf_hub_download
from openai import OpenAI
from openpyxl import Workbook

from config import HF_JOB_INFO_FILE, HF_RESULTS_FILE, JUDGE_MODEL, RESULTS_DIR

JUDGE_PROMPT = """You are grading answers from a support assistant for the Internal \
Logistics Platform (ILP) against a reference answer.

Question: {question}
Reference answer: {reference}

Candidate answer A (base model, before fine-tuning): {answer_a}
Candidate answer B (LoRA fine-tuned model, after fine-tuning): {answer_b}

Score each candidate 1-5 for factual accuracy and completeness versus the reference \
answer (5 = matches the reference closely, 1 = wrong or unrelated). Reply with ONLY a \
JSON object: {{"score_a": <int>, "score_b": <int>, "comment": "<one short sentence>"}}"""


def judge(client, question, reference, answer_a, answer_b):
    prompt = JUDGE_PROMPT.format(
        question=question, reference=reference, answer_a=answer_a, answer_b=answer_b
    )
    response = client.chat.completions.create(
        model=JUDGE_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)


def main():
    load_dotenv()

    if not HF_JOB_INFO_FILE.exists():
        raise SystemExit("No hf_finetune_job.json found. Run 05_run_hf_finetune.py first.")
    job_info = json.loads(HF_JOB_INFO_FILE.read_text(encoding="utf-8"))
    if job_info.get("stage") != "COMPLETED":
        raise SystemExit(f"Job stage is {job_info.get('stage')!r}, not COMPLETED yet.")
    model_repo = job_info["model_repo"]

    print(f"[1/3] Downloading results.json from {model_repo}")
    results_path = hf_hub_download(repo_id=model_repo, filename="results.json")
    with open(results_path, encoding="utf-8") as f:
        rows = json.load(f)
    print(f"      -> {len(rows)} held-out questions")

    print("[2/3] Judging before vs. after answers")
    client = OpenAI()
    for i, row in enumerate(rows, start=1):
        print(f"      question {i}/{len(rows)}: {row['question'][:70]}...")
        verdict = judge(client, row["question"], row["reference"], row["before_answer"], row["after_answer"])
        row["before_score"] = verdict["score_a"]
        row["after_score"] = verdict["score_b"]
        row["comment"] = verdict["comment"]

    print("[3/3] Writing results to Excel")
    RESULTS_DIR.mkdir(exist_ok=True)
    wb = Workbook()

    ws = wb.active
    ws.title = "Comparison"
    ws.append(
        [
            "Question",
            "Reference answer",
            "Before (base Qwen2.5-1.5B-Instruct)",
            "Before score (1-5)",
            "After (LoRA fine-tuned)",
            "After score (1-5)",
            "Improvement",
            "Judge comment",
        ]
    )
    for row in rows:
        ws.append(
            [
                row["question"],
                row["reference"],
                row["before_answer"],
                row["before_score"],
                row["after_answer"],
                row["after_score"],
                row["after_score"] - row["before_score"],
                row["comment"],
            ]
        )

    avg_before = sum(r["before_score"] for r in rows) / len(rows)
    avg_after = sum(r["after_score"] for r in rows) / len(rows)
    wins = sum(1 for r in rows if r["after_score"] > r["before_score"])
    ties = sum(1 for r in rows if r["after_score"] == r["before_score"])
    losses = sum(1 for r in rows if r["after_score"] < r["before_score"])

    summary = wb.create_sheet("Summary")
    summary.append(["Metric", "Value"])
    summary.append(["Base model", job_info["base_model"]])
    summary.append(["Method", "LoRA (QLoRA, 4-bit) via Hugging Face Jobs"])
    summary.append(["Questions evaluated", len(rows)])
    summary.append(["Average score - before fine-tuning", round(avg_before, 2)])
    summary.append(["Average score - after fine-tuning", round(avg_after, 2)])
    summary.append(["Fine-tuned better", wins])
    summary.append(["Tie", ties])
    summary.append(["Fine-tuned worse", losses])

    wb.save(HF_RESULTS_FILE)
    print(f"      -> {HF_RESULTS_FILE}")
    print(f"\nAverage score: before={avg_before:.2f}  after={avg_after:.2f}")
    print(f"After better on {wins}/{len(rows)}, tied on {ties}, worse on {losses}")


if __name__ == "__main__":
    main()
