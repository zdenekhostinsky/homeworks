"""Step 1: turn ILPDocumentation_dataset.jsonl into OpenAI fine-tuning files."""

import json
import random

from config import (
    DATA_DIR,
    EVAL_FILE,
    EVAL_SIZE,
    RANDOM_SEED,
    SOURCE_DATASET,
    SYSTEM_PROMPT,
    TRAIN_FILE,
    VALID_FILE,
    VALID_RATIO,
)


def load_pairs():
    pairs = []
    with open(SOURCE_DATASET, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            question = record["question"].strip()
            answer = record["answer"].strip()
            if question and answer:
                pairs.append((question, answer))
    return pairs


def to_chat_example(question, answer):
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer},
        ]
    }


def write_jsonl(path, records):
    with open(path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def main():
    print(f"[1/4] Loading Q&A pairs from {SOURCE_DATASET}")
    pairs = load_pairs()
    print(f"      -> {len(pairs)} pairs loaded")

    print("[2/4] Shuffling with a fixed seed and splitting eval / train / valid")
    rng = random.Random(RANDOM_SEED)
    rng.shuffle(pairs)

    eval_pairs = pairs[:EVAL_SIZE]
    rest = pairs[EVAL_SIZE:]
    n_valid = max(1, int(len(rest) * VALID_RATIO))
    valid_pairs = rest[:n_valid]
    train_pairs = rest[n_valid:]
    print(f"      -> train={len(train_pairs)}  valid={len(valid_pairs)}  eval(held out)={len(eval_pairs)}")

    print("[3/4] Writing OpenAI chat-format JSONL files")
    DATA_DIR.mkdir(exist_ok=True)
    write_jsonl(TRAIN_FILE, [to_chat_example(q, a) for q, a in train_pairs])
    write_jsonl(VALID_FILE, [to_chat_example(q, a) for q, a in valid_pairs])
    write_jsonl(EVAL_FILE, [{"question": q, "answer": a} for q, a in eval_pairs])
    print(f"      -> {TRAIN_FILE}")
    print(f"      -> {VALID_FILE}")
    print(f"      -> {EVAL_FILE}  (kept aside, never used for training)")

    print("[4/4] Sample training example:")
    print(json.dumps(to_chat_example(*train_pairs[0]), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
