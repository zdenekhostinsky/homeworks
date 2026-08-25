# Lekce 1 - Agent s nastrojem na pocasi

Skript zavola LLM API (Claude), da mu k dispozici nastroj `get_weather` a
necha model samotny rozhodnout, jestli je pro odpoved na dany prompt
potreba pocasi zjistit:

- Pokud dotaz na pocasi zavisi (napr. *"kdy je nejlepsi vydat se na vylet v
  pristim tydnu"*), model zavola nastroj `get_weather`, ktery stahne
  realnou predpoved z [Open-Meteo](https://open-meteo.com/) (geokodovani
  mesta + denni predpoved az na 16 dni dopredu - zdarma, bez API klice).
  Vysledek nastroje se posle zpet modelu a ten z nej sestavi finalni
  odpoved (napr. doporuci konkretni den s nejmensi sanci na dest).
- Pokud dotaz s pocasim nesouvisi, nebo mu model nerozumi, nastroj se
  nepouzije a vrati se rovnou odpoved z LLM API.

## Instalace

```bash
cd AIAgenti/Lekce1
pip install -r requirements.txt
cp .env.example .env
# do .env doplnit ANTHROPIC_API_KEY (stejny klic jako v AIDevelopper/Lekce9)
```

## Spusteni

```bash
python weather_agent.py "Kdy je nejlepsi vydat se na vylet v pristim tydnu?"
```

Nebo interaktivne (bez argumentu skript o dotaz sam pozada):

```bash
python weather_agent.py
```

S prepinacem `--verbose` (nebo `-v`) skript navic na stderr vypise, jestli
model nastroj zavolal a s jakymi parametry - hodi se na ukazku, ze o
pouziti nastroje rozhoduje model sam:

```bash
python weather_agent.py --verbose "Kdy je nejlepsi vydat se na vylet v pristim tydnu?"
```

```
[agent] Model vola nastroj get_weather s parametry {"city": "Praha", "days_ahead": 7}
[agent] Nastroj vratil 7 dni predpovedi pro Praha, Česko.
[agent] Posilam vysledek nastroje zpet modelu.
```

Priklady promptu:

- `"Kdy je nejlepsi vydat se na vylet v pristim tydnu?"` -> pouzije se
  nastroj `get_weather` (bez uvedeneho mesta se pouzije Praha).
- `"Jake bude pocasi v Brne pristich 5 dni?"` -> nastroj se pouzije s
  mestem Brno a `days_ahead=5`.
- `"Napis mi vtip o programatorech."` -> s pocasim nesouvisi, nastroj se
  nepouzije, odpoved vrati primo LLM.

## Poznamka k API klici

Skript pouziva Anthropic Claude API (`ANTHROPIC_API_KEY`) - stejny typ
klice, jaky se pouziva v `AIDevelopper/Lekce9`. Nastroj na pocasi sam o
sobe zadny API klic nepotrebuje (Open-Meteo je verejne a zdarma).
