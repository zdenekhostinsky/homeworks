# Lekce 5 - Tvorba no-code agenta

## Zadani

Navrhnout a vytvorit agenta v libovolne "No code" platforme, ktery pracuje s
databazi, pouziva nastroje a odpovida na dotazy pres LLM. Format: JSON soubor
s definici workflow.

Zvolena platforma: **N8N**. Cilem neni funkcni nasazeni (zadne skutecne
credentials, servery ani cilove pocitace za tim nestoji), ale nastreleni
architektury jako importovatelny `workflow.n8n.json`.

## Napad: "AI sekretarka" jako multi-PC dispecer ukolu

Osobni asistent, ktery:

1. periodicky cte signaly ze dvou zdroju - **Microsoft Teams** (chat zpravy
   pres Microsoft Graph) a **Claude Code session logy** (co jsem si rekl/
   napsal behem prace),
2. pro kazdy signal necha **LLM (Claude) rozhodnout**, jestli jde o ukol k
   provedeni, a pokud ano, **na ktery pocitac** patri - podle registru
   pocitacu s jejich schopnostmi/instrukcemi ulozeneho v databazi,
3. ukol **dispatchne** na spravny pocitac (kde bezi lehky "child agent" -
   webhook listener, ktery prikaz prevezme a provede),
4. vysledek/rozhodnuti **zaloguje do DB** a posle **potvrzeni zpet do Teams**.

Princip rozhodovani "pouzit nastroj, nebo ne / ktery nastroj" je stejny jako
v [Lekci 1](../Lekce1/README.md) (tam LLM rozhoduje o `get_weather`), jen
misto jednoho nastroje LLM vybira mezi vice cilovymi pocitaci na zaklade
volneho textu instrukci v registru - viz system prompt v nodu
`LLM - klasifikace + vyber pocitace`.

## Architektura (nody v `workflow.n8n.json`)

```
Cron (15 min)
  |-> Precti Teams zpravy (MS Graph)        --\
  |-> Precti Claude Code session log        --+--> Merge signalu
                                                       |
                                       Postgres: Registr pocitacu
                                                       |
                                       Priprav kontext pro LLM (Code node)
                                                       |
                                  LLM - klasifikace + vyber pocitace (Claude)
                                                       |
                                             Parsuj LLM JSON (Code node)
                                                       |
                                             Ma to byt ukol? (If)
                                                       |
                                       Switch podle cilove pocitace
                                        /        |         \
                             notebook   domaci-pc   pracovni-pc
                             (HTTP dispatch na child agenta kazdeho pocitace)
                                        \        |         /
                                       Postgres: Zaloguj ukol
                                                       |
                                       Potvrzeni zpet do Teams
```

**Databaze (Postgres):**
- `computer_registry` - `computer_name, capabilities, instructions, webhook_url, is_online`
  (co dany pocitac umi a za jakych podminek na nej ukoly posilat - toto ctou
  LLM node jako kontext pro rozhodovani)
- `task_log` - `task, target_computer, reason, dispatched_at` (audit trail)

**Nastroje, ktere agent pouziva:**
- Microsoft Graph (cteni Teams, pripadne pozdeji i zapis potvrzeni)
- Postgres (registr pocitacu + log)
- Anthropic API / Claude (LLM rozhodovani - "je to ukol? pro koho?")
- HTTP webhook na kazdem cilovem pocitaci (child agent)

## Co v tomto nastrelu chybi (vedome, mimo rozsah ukolu)

- Realny "child agent" na jednotlivych pocitacich (jen webhook stub v nodu
  `Dispatch -> ...`).
- Autentizace/credentials (MS Graph OAuth2, Anthropic API key, Postgres) -
  v n8n by se navazaly pres Credentials store, tady jen typ credential.
- Deduplikace ukolu, retry logika, chybove vetve (napr. cilovy pocitac je
  offline).
- Odesilani zpravy do Teams je outward-facing akce - v realnem nasazeni by
  mela projit potvrzenim, ne bezet automaticky (viz poznamka v nodu
  `Potvrzeni zpet do Teams`).

## Import

`workflow.n8n.json` lze naimportovat primo do n8n (Import from File /
Import from URL). Bez nastavenych credentials a bezicich child agentu
nepobezi end-to-end, ale strukturu a rozhodovaci logiku ukazuje cela.
