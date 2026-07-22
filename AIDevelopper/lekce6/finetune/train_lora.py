# /// script
# dependencies = [
#     "trl>=0.12.0",
#     "peft>=0.13.0",
#     "bitsandbytes>=0.44.0",
#     "datasets>=3.0.0",
#     "huggingface_hub>=0.26.0",
# ]
# ///
"""Runs inside a Hugging Face Job: generate 'before' answers, LoRA fine-tune, generate 'after' answers."""

import argparse
import json

import torch
from datasets import load_dataset
from huggingface_hub import HfApi
from peft import LoraConfig
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from trl import SFTConfig, SFTTrainer

SYSTEM_PROMPT = (
    "You are a support assistant for the Internal Logistics Platform (ILP), "
    "the company's core logistics platform. Answer questions about the ILP "
    "accurately and concisely, based on its technical documentation."
)


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--base-model", required=True)
    p.add_argument("--dataset-repo", required=True)
    p.add_argument("--model-repo", required=True)
    return p.parse_args()


def generate_answers(model, tokenizer, questions, label):
    model.eval()
    answers = []
    for i, question in enumerate(questions, start=1):
        print(f"      [{label}] question {i}/{len(questions)}: {question[:70]}...")
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ]
        prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
        with torch.no_grad():
            output = model.generate(
                **inputs,
                max_new_tokens=300,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id,
            )
        text = tokenizer.decode(output[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
        answers.append(text.strip())
    return answers


def main():
    args = parse_args()

    print(f"[1/6] Loading tokenizer and base model: {args.base_model}")
    tokenizer = AutoTokenizer.from_pretrained(args.base_model)
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
    )
    model = AutoModelForCausalLM.from_pretrained(
        args.base_model, quantization_config=bnb_config, device_map="auto"
    )

    print(f"[2/6] Loading dataset: {args.dataset_repo}")
    dataset = load_dataset(args.dataset_repo)
    eval_dataset = load_dataset(args.dataset_repo, "eval")["eval"]
    eval_questions = eval_dataset["question"]
    eval_references = eval_dataset["answer"]
    print(f"      train={len(dataset['train'])}  validation={len(dataset['validation'])}  eval={len(eval_questions)}")

    print("[3/6] Generating BEFORE answers with the base model")
    before_answers = generate_answers(model, tokenizer, eval_questions, "before")

    print("[4/6] LoRA fine-tuning")
    peft_config = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        target_modules="all-linear",
        task_type="CAUSAL_LM",
    )
    sft_config = SFTConfig(
        output_dir="/tmp/output",
        num_train_epochs=3,
        per_device_train_batch_size=4,
        gradient_accumulation_steps=4,
        learning_rate=2e-4,
        logging_steps=10,
        eval_strategy="epoch",
        bf16=True,
        max_length=512,
        report_to="none",
        push_to_hub=True,
        hub_model_id=args.model_repo,
        hub_private_repo=True,
    )
    trainer = SFTTrainer(
        model=model,
        args=sft_config,
        train_dataset=dataset["train"],
        eval_dataset=dataset["validation"],
        peft_config=peft_config,
    )
    trainer.train()

    print("[5/6] Generating AFTER answers with the fine-tuned model")
    after_answers = generate_answers(trainer.model, tokenizer, eval_questions, "after")

    print(f"[6/6] Pushing adapter to https://huggingface.co/{args.model_repo} and uploading results.json")
    HfApi().create_repo(args.model_repo, private=True, exist_ok=True)
    trainer.push_to_hub()

    results = [
        {
            "question": q,
            "reference": r,
            "before_answer": b,
            "after_answer": a,
        }
        for q, r, b, a in zip(eval_questions, eval_references, before_answers, after_answers)
    ]
    with open("/tmp/results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    HfApi().upload_file(
        path_or_fileobj="/tmp/results.json",
        path_in_repo="results.json",
        repo_id=args.model_repo,
        repo_type="model",
    )
    print("Done.")


if __name__ == "__main__":
    main()
