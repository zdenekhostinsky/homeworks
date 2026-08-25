"""Lekce 1 - AI Agenti: agent s nastrojem na pocasi.

Skript dostane textovy prompt a posle ho LLM (Claude) spolu s definici
nastroje `get_weather`. Model sam vyhodnoti, jestli dotaz souvisi s pocasim
(napr. planovani vyletu) - pokud ano, zavola nastroj, jeho vysledek se posle
zpet modelu a ten z nej sestavi finalni odpoved. Pokud dotaz s pocasim
nesouvisi (nebo mu model nerozumi), vrati se rovnou odpoved z LLM API bez
volani nastroje.

Pouziti:
    python weather_agent.py "Kdy je nejlepsi vydat se na vylet v pristim tydnu?"
    python weather_agent.py            # zepta se interaktivne

Nastroj pro pocasi vyuziva volne dostupne Open-Meteo API (geokodovani nazvu
mesta + predpoved az na 16 dni dopredu), takze funguje bez dalsiho API
klice - staci mit v .env nastaveny ANTHROPIC_API_KEY.
"""

import json
import os
import sys

import requests
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv(override=True)

MODEL_NAME = "claude-haiku-4-5-20251001"
DEFAULT_CITY = "Praha"

# Mapovani WMO weather kodu (pouzivanych Open-Meteo) na cesky popis.
WMO_DESCRIPTIONS = {
    0: "jasno",
    1: "prevazne jasno",
    2: "polojasno",
    3: "zatazeno",
    45: "mlha",
    48: "mrznouci mlha",
    51: "slabe mrholeni",
    53: "mrholeni",
    55: "silne mrholeni",
    56: "slabe mrznouci mrholeni",
    57: "silne mrznouci mrholeni",
    61: "slaby dest",
    63: "dest",
    65: "silny dest",
    66: "slaby mrznouci dest",
    67: "silny mrznouci dest",
    71: "slabe snezeni",
    73: "snezeni",
    75: "silne snezeni",
    77: "snehova zrna",
    80: "slabe prehanky",
    81: "prehanky",
    82: "silne prehanky",
    85: "slabe snehove prehanky",
    86: "silne snehove prehanky",
    95: "bourka",
    96: "bourka s kroupami",
    99: "silna bourka s kroupami",
}


def geocode_city(city: str) -> dict | None:
    """Najde zemepisnou sirku/delku mesta podle nazvu (Open-Meteo geocoding)."""
    resp = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": city, "count": 1, "language": "cs", "format": "json"},
        timeout=10,
    )
    resp.raise_for_status()
    results = resp.json().get("results")
    if not results:
        return None
    r = results[0]
    return {
        "latitude": r["latitude"],
        "longitude": r["longitude"],
        "name": r["name"],
        "country": r.get("country", ""),
    }


def fetch_forecast(latitude: float, longitude: float, days: int) -> list[dict]:
    """Stahne denni predpoved pocasi z Open-Meteo pro dane souradnice."""
    days = max(1, min(days, 16))
    resp = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": latitude,
            "longitude": longitude,
            "daily": (
                "weathercode,temperature_2m_max,temperature_2m_min,"
                "precipitation_probability_max,windspeed_10m_max"
            ),
            "timezone": "auto",
            "forecast_days": days,
        },
        timeout=10,
    )
    resp.raise_for_status()
    daily = resp.json()["daily"]
    return [
        {
            "datum": daily["time"][i],
            "pocasi": WMO_DESCRIPTIONS.get(daily["weathercode"][i], f"kod {daily['weathercode'][i]}"),
            "teplota_max_c": daily["temperature_2m_max"][i],
            "teplota_min_c": daily["temperature_2m_min"][i],
            "pravdepodobnost_srazek_pct": daily["precipitation_probability_max"][i],
            "vitr_max_kmh": daily["windspeed_10m_max"][i],
        }
        for i in range(len(daily["time"]))
    ]


def get_weather(city: str = DEFAULT_CITY, days_ahead: int = 7) -> dict:
    """Nastroj volany modelem: vrati denni predpoved pocasi pro dane mesto."""
    try:
        location = geocode_city(city)
    except requests.RequestException as exc:
        return {"error": f"Nepodarilo se najit mesto '{city}': {exc}"}
    if location is None:
        return {"error": f"Mesto '{city}' se nepodarilo najit."}
    try:
        forecast = fetch_forecast(location["latitude"], location["longitude"], days_ahead)
    except requests.RequestException as exc:
        return {"error": f"Nepodarilo se nacist predpoved pocasi: {exc}"}
    return {"mesto": location["name"], "zeme": location["country"], "predpoved": forecast}


TOOL_DEFINITION = {
    "name": "get_weather",
    "description": (
        "Vrati denni predpoved pocasi (teplota, srazky, vitr) pro zadane "
        "mesto na nekolik dni dopredu. Pouzij tento nastroj vzdy, kdyz se "
        "uzivatel pta na pocasi, nebo se pta na neco, co na pocasi zavisi "
        "(napr. kdy je nejlepsi den na vylet, vyjizdku na kole apod.)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "description": (
                    "Nazev mesta, pro ktere se ma pocasi zjistit. Pokud ho "
                    "uzivatel v dotazu neuvede, pouzij 'Praha'."
                ),
            },
            "days_ahead": {
                "type": "integer",
                "description": (
                    "Na kolik dni dopredu chce uzivatel predpoved (1-16). "
                    "Pro dotazy typu 'pristi tyden' pouzij 7."
                ),
            },
        },
        "required": ["city", "days_ahead"],
    },
}

SYSTEM_PROMPT = (
    "Jsi uzitecny asistent, ktery odpovida cesky. Pokud se uzivateluv dotaz "
    "tyka pocasi, nebo na pocasi zavisi (napr. planovani vyletu, obleceni, "
    "sportu venku), pouzij nastroj get_weather a odpoved postav na realnych "
    "datech, ktera vrati - doporuceni zduvodni (napr. nejnizsi "
    "pravdepodobnost srazek, prijemna teplota). Pokud dotaz s pocasim "
    "nesouvisi, nebo mu nerozumis, odpovez normalne bez pouziti nastroje."
)


def _extract_text(response) -> str:
    return "\n".join(block.text for block in response.content if block.type == "text").strip()


def run_agent(prompt: str, client: Anthropic) -> str:
    messages = [{"role": "user", "content": prompt}]

    response = client.messages.create(
        model=MODEL_NAME,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        tools=[TOOL_DEFINITION],
        messages=messages,
    )

    tool_calls = [block for block in response.content if block.type == "tool_use"]
    if response.stop_reason != "tool_use" or not tool_calls:
        # Dotaz se pocasi netykal (nebo mu model nerozumel) - vracime
        # rovnou odpoved z LLM API bez volani nastroje.
        return _extract_text(response)

    messages.append({"role": "assistant", "content": response.content})

    tool_results = []
    for block in tool_calls:
        if block.name == "get_weather":
            result = get_weather(
                city=block.input.get("city", DEFAULT_CITY),
                days_ahead=int(block.input.get("days_ahead", 7)),
            )
        else:
            result = {"error": f"Neznamy nastroj: {block.name}"}
        tool_results.append(
            {
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(result, ensure_ascii=False),
            }
        )

    # Vysledek nastroje se posle zpet LLM, aby z nej sestavil finalni odpoved.
    messages.append({"role": "user", "content": tool_results})

    final_response = client.messages.create(
        model=MODEL_NAME,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        tools=[TOOL_DEFINITION],
        messages=messages,
    )
    return _extract_text(final_response)


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print(
            "Chybi ANTHROPIC_API_KEY. Zkopiruj .env.example do .env a "
            "vyplnit klic (stejny typ klice jako v AIDevelopper/Lekce9).",
            file=sys.stderr,
        )
        sys.exit(1)

    prompt = " ".join(sys.argv[1:]).strip() if len(sys.argv) > 1 else input("Zadej dotaz: ").strip()
    if not prompt:
        print("Prazdny dotaz.", file=sys.stderr)
        sys.exit(1)

    client = Anthropic(api_key=api_key)
    print(run_agent(prompt, client))


if __name__ == "__main__":
    main()
