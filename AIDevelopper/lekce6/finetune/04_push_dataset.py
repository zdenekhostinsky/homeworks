"""Step 4: push the train/valid split to a private HF dataset repo so the cloud job can read it."""

from datasets import Dataset, DatasetDict
from dotenv import load_dotenv
from huggingface_hub import HfApi

from config import EVAL_FILE, HF_DATASET_REPO_SUFFIX, TRAIN_FILE, VALID_FILE


def main():
    load_dotenv()
    api = HfApi()
    username = api.whoami()["name"]
    repo_id = f"{username}/{HF_DATASET_REPO_SUFFIX}"

    print(f"[1/2] Loading {TRAIN_FILE.name}, {VALID_FILE.name} and {EVAL_FILE.name}")
    ds = DatasetDict(
        {
            "train": Dataset.from_json(str(TRAIN_FILE)),
            "validation": Dataset.from_json(str(VALID_FILE)),
        }
    )
    eval_ds = Dataset.from_json(str(EVAL_FILE))  # different schema (question/answer), own config
    print(f"      -> train={len(ds['train'])}  validation={len(ds['validation'])}  eval(held out)={len(eval_ds)}")

    print(f"[2/2] Pushing to https://huggingface.co/datasets/{repo_id} (private)")
    ds.push_to_hub(repo_id, private=True)
    eval_ds.push_to_hub(repo_id, config_name="eval", split="eval", private=True)
    print("      -> done")


if __name__ == "__main__":
    main()
