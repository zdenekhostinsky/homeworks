# Lekce 6 – Fine-tuning

Cíl: fine-tunovat model na interní znalostní bázi (ILP – Internal Logistics Platform
dokumentace), porovnat odpovědi před/po a vyhodnotit pomocí benchmarkingu.

## Zdrojová data

738 Q&A párů vygenerovaných z ~275stránkové interní technické dokumentace ILP
(zdrojový dataset mimo tento balíček – interní/proprietární materiál zaměstnavatele).

Rozdělení (`01_prepare_dataset.py`, seed=42):

| split | počet | použití |
|---|---|---|
| train | 647 | trénink |
| validation | 71 | validace během tréninku |
| eval | 20 | odloženo, nikdy netrénováno – použito na benchmark před/po |

## Zvolená metoda a proč

Plán byl použít OpenAI fine-tuning API (`gpt-4o-mini`) – nejlevnější a nejjednodušší
varianta. Při pokusu o spuštění (`02_run_finetune.py`) ale OpenAI vrátilo:

> `403 training_not_available` – "OpenAI is winding down the fine-tuning platform and
> your organization is no longer able to create new fine-tuning training jobs."

OpenAI od 7. 5. 2026 postupně utlumuje self-serve fine-tuning a nové organizace už
nemohou zakládat joby. Přešlo se proto na **Hugging Face Jobs + LoRA (QLoRA)**:

- **Base model:** `Qwen/Qwen2.5-1.5B-Instruct` (malý open model, běží i na jedné T4 GPU)
- **Metoda:** LoRA (r=16, alpha=32) přes 4-bit QLoRA kvantizaci, 3 epochy
- **Infrastruktura:** [Hugging Face Jobs](https://huggingface.co/docs/huggingface_hub/guides/jobs)
  (`hf jobs uv run`), GPU flavor `t4-medium`, cena ~$0.60/h
- **Cena celého tréninku:** ~25 min běhu ≈ **$0.25**

## Pipeline (kroky)

| skript | co dělá |
|---|---|
| `01_prepare_dataset.py` | rozdělí zdrojová Q&A data na train/valid/eval JSONL |
| `02_run_finetune.py`, `03_evaluate.py` | **OpenAI cesta – nefunkční**, ponecháno jako doklad pokusu |
| `04_push_dataset.py` | nahraje train/valid/eval na privátní HF dataset repo |
| `train_lora.py` | běží uvnitř HF Jobu: vygeneruje odpovědi "před", QLoRA fine-tuning, vygeneruje odpovědi "po", nahraje adapter + `results.json` na HF Hub |
| `05_run_hf_finetune.py` | odpálí a sleduje `train_lora.py` na HF Jobs |
| `06_evaluate_hf.py` | stáhne `results.json`, nechá odpovědi ohodnotit LLM-judgem (`gpt-4o-mini`, 1–5 bodů oproti referenční odpovědi) a vytvoří `results/comparison_hf.xlsx` |

### Reprodukce

```bash
pip install -r requirements.txt
cp .env.example .env   # doplnit OPENAI_API_KEY (judge) a HF_TOKEN (Jobs, write + Jobs scope)

python 01_prepare_dataset.py
python 04_push_dataset.py
python 05_run_hf_finetune.py   # ~25 min, ~$0.25 na HF Jobs
python 06_evaluate_hf.py       # pár desítek centů na OpenAI (jen judge, ne fine-tuning)
```

## Výsledky benchmarku (20 odložených otázek)

| metrika | před | po |
|---|---|---|
| průměrné skóre (1–5, judge = gpt-4o-mini) | **2.15** | **2.95** |
| lepší po fine-tuningu | – | 15/20 |
| shoda | – | 1/20 |
| horší po fine-tuningu | – | 4/20 |

Zlepšení o **+37 % relativně**. Agregovaná čísla jsou v `results/comparison_summary.xlsx`.
Kompletní tabulka se všemi 20 otázkami, referenčními odpověďmi, odpověďmi před/po a
bodováním (`results/comparison_hf.xlsx`) obsahuje reálný text z interní dokumentace,
takže není součástí tohoto repozitáře – jen v balíčku předaném přímo lektorovi.

Kvalitativně: bázový model o interním systému ILP nic nevěděl a odpovídal obecnými,
vágními frázemi. Po fine-tuningu začal používat konkrétní terminologii a fakta z
dokumentace – ne vždy dokonale přesně (menší model, jen 3 epochy), ale jasně vidět, že
fine-tuning znalosti skutečně "natlačil" do vah modelu.

## Poznámka k datům

Zdrojová dokumentace ILP i z ní odvozený dataset a plná tabulka odpovědí obsahují
interní/proprietární detaily zaměstnavatele, proto nejsou součástí tohoto (veřejně
sdíleného) repozitáře – jen v balíčku předaném přímo lektorovi.
