"""Step 3: compare base vs fine-tuned model on held-out questions and score them."""

import json

from dotenv import load_dotenv
from openai import OpenAI
from openpyxl import Workbook

from config import BASE_MODEL, EVAL_FILE, JOB_INFO_FILE, RESULTS_DIR, RESULTS_FILE, SYSTEM_PROMPT

JUDGE_PROMPT = """You are grading answers from a support assistant for the ILP Logistics \
Application (ILP) against a reference answer.

Question: {question}
Reference answer: {reference}

Candidate answer A (base model): {answer_a}
Candidate answer B (fine-tuned model): {answer_b}

Score each candidate 1-5 for factual accuracy and completeness versus the reference \
answer (5 = matches the reference closely, 1 = wrong or unrelated). Reply with ONLY a \
JSON object: {{"score_a": <int>, "score_b": <int>, "comment": "<one short sentence>"}}"""


def load_eval_pairs():
    pairs = []
    with open(EVAL_FILE, encoding="utf-8") as f:
        for line in f:
            record = json.loads(line)
            pairs.append((record["question"], record["answer"]))
    return pairs


def ask(client, model, question):
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        temperature=0,
    )
    return response.choices[0].message.content.strip()


def judge(client, question, reference, answer_a, answer_b):
    prompt = JUDGE_PROMPT.format(
        question=question, reference=reference, answer_a=answer_a, answer_b=answer_b
    )
    response = client.chat.completions.create(
        model=BASE_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)


def main():
    load_dotenv()
    client = OpenAI()

    if not JOB_INFO_FILE.exists():
        raise SystemExit("No finetune_job.json found. Run 02_run_finetune.py first.")
    job_info = json.loads(JOB_INFO_FILE.read_text(encoding="utf-8"))
    ft_model = job_info.get("fine_tuned_model")
    if not ft_model:
        raise SystemExit("Fine-tuned model id missing. Wait for 02_run_finetune.py to finish.")

    print(f"Base model:       {BASE_MODEL}")
    print(f"Fine-tuned model: {ft_model}")

    pairs = load_eval_pairs()
    print(f"[1/2] Running {len(pairs)} held-out questions through both models")

    rows = []
    for i, (question, reference) in enumerate(pairs, start=1):
        print(f"      question {i}/{len(pairs)}: {question[:70]}...")
        base_answer = ask(client, BASE_MODEL, question)
        ft_answer = ask(client, ft_model, question)
        verdict = judge(client, question, reference, base_answer, ft_answer)
        rows.append(
            {
                "question": question,
                "reference": reference,
                "base_answer": base_answer,
                "base_score": verdict["score_a"],
                "ft_answer": ft_answer,
                "ft_score": verdict["score_b"],
                "comment": verdict["comment"],
            }
        )

    print("[2/2] Writing results to Excel")
    RESULTS_DIR.mkdir(exist_ok=True)
    wb = Workbook()

    ws = wb.active
    ws.title = "Comparison"
    ws.append(
        [
            "Question",
            "Reference answer",
            "Base answer (gpt-4o-mini)",
            "Base score (1-5)",
            "Fine-tuned answer",
            "Fine-tuned score (1-5)",
            "Improvement",
            "Judge comment",
        ]
    )
    for row in rows:
        ws.append(
            [
                row["question"],
                row["reference"],
                row["base_answer"],
                row["base_score"],
                row["ft_answer"],
                row["ft_score"],
                row["ft_score"] - row["base_score"],
                row["comment"],
            ]
        )

    avg_base = sum(r["base_score"] for r in rows) / len(rows)
    avg_ft = sum(r["ft_score"] for r in rows) / len(rows)
    wins = sum(1 for r in rows if r["ft_score"] > r["base_score"])
    ties = sum(1 for r in rows if r["ft_score"] == r["base_score"])
    losses = sum(1 for r in rows if r["ft_score"] < r["base_score"])

    summary = wb.create_sheet("Summary")
    summary.append(["Metric", "Value"])
    summary.append(["Questions evaluated", len(rows)])
    summary.append(["Average score - base model", round(avg_base, 2)])
    summary.append(["Average score - fine-tuned model", round(avg_ft, 2)])
    summary.append(["Fine-tuned better", wins])
    summary.append(["Tie", ties])
    summary.append(["Fine-tuned worse", losses])

    wb.save(RESULTS_FILE)
    print(f"      -> {RESULTS_FILE}")
    print(f"\nAverage score: base={avg_base:.2f}  fine-tuned={avg_ft:.2f}")
    print(f"Fine-tuned better on {wins}/{len(rows)}, tied on {ties}, worse on {losses}")


if __name__ == "__main__":
    main()
