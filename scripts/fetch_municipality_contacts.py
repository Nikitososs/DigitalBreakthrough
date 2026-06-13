"""Fetch MO administration contacts from gosweb.gosuslugi.ru (one-off research helper)."""
from __future__ import annotations

import json
import re
import ssl
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "_municipality_contacts_raw.json"

# Excel/cache name → gosweb host slug (without domain)
MUNICIPALITY_SITES: dict[str, dict[str, str]] = {
    "Азовский немецкий национальный район": {
        "slug": "azovskij-nem-nac-r52",
        "administration": "Администрация Азовского немецкого национального муниципального района Омской области",
    },
    "Большереченский район": {
        "slug": "bolsherechenskij-r52",
        "administration": "Администрация Большереченского муниципального района Омской области",
    },
    "Большеуковский район": {
        "slug": "bolsheukovskij-r52",
        "administration": "Администрация Большеуковского муниципального района Омской области",
    },
    "Горьковский район": {
        "slug": "gorkovskij-r52",
        "administration": "Администрация Горьковского муниципального района Омской области",
    },
    "Знаменский район": {
        "slug": "znamenskij-r52",
        "administration": "Администрация Знаменского муниципального района Омской области",
    },
    "Исилькульский район": {
        "slug": "isilkulskij-r52",
        "administration": "Администрация Исилькульского муниципального района Омской области",
    },
    "Калачинский район": {
        "slug": "kalachinskij-r52",
        "administration": "Администрация Калачинского муниципального района Омской области",
    },
    "Колосовский район": {
        "slug": "kolosovskij-r52",
        "administration": "Администрация Колосовского муниципального района Омской области",
    },
    "Кормиловский район": {
        "slug": "kormilovskij-r52",
        "administration": "Администрация Кормиловского муниципального района Омской области",
    },
    "Крутинский район": {
        "slug": "krutinskij-r52",
        "administration": "Администрация Крутинского муниципального района Омской области",
    },
    "Любинский район": {
        "slug": "lyubinskij-r52",
        "administration": "Администрация Любинского муниципального района Омской области",
    },
    "Марьяновский район": {
        "slug": "maryanovskij-r52",
        "administration": "Администрация Марьяновского муниципального района Омской области",
    },
    "Москаленский район": {
        "slug": "moskalenskij-r52",
        "administration": "Администрация Москаленского муниципального района Омской области",
    },
    "Муромцевский район": {
        "slug": "muromtsevskij-r52",
        "administration": "Администрация Муромцевского муниципального района Омской области",
    },
    "Называевский район": {
        "slug": "nazyvaevskij-r52",
        "administration": "Администрация Называевского муниципального района Омской области",
    },
    "Нижнеомский район": {
        "slug": "nizhneomskij-r52",
        "administration": "Администрация Нижнеомского муниципального района Омской области",
    },
    "Нововаршавский район": {
        "slug": "novovarshavskij-r52",
        "administration": "Администрация Нововаршавского муниципального района Омской области",
    },
    "Одесский район": {
        "slug": "odesskij-r52",
        "administration": "Администрация Одесского муниципального района Омской области",
    },
    "Оконешниковский район": {
        "slug": "okoneshnikovskij-r52",
        "administration": "Администрация Оконешниковского муниципального района Омской области",
    },
    "Омский район": {
        "slug": "omskij-r52",
        "administration": "Администрация Омского муниципального района Омской области",
    },
    "Павлоградский район": {
        "slug": "pavlogradka-r52",
        "administration": "Администрация Павлоградского муниципального района Омской области",
    },
    "Полтавский район": {
        "slug": "poltavskij-r52",
        "administration": "Администрация Полтавского муниципального района Омской области",
    },
    "Русско-Полянский район": {
        "slug": "russko-polyanskij-r52",
        "administration": "Администрация Русско-Полянского муниципального района Омской области",
    },
    "Саргатский район": {
        "slug": "sargatskij-r52",
        "administration": "Администрация Саргатского муниципального района Омской области",
    },
    "Седельниковский район": {
        "slug": "sedelnikovskij-r52",
        "administration": "Администрация Седельниковского муниципального района Омской области",
    },
    "Таврический район": {
        "slug": "tavricheskij-r52",
        "administration": "Администрация Таврического муниципального района Омской области",
    },
    "Тарский район": {
        "slug": "tarskij-r52",
        "administration": "Администрация Тарского муниципального района Омской области",
    },
    "Тевризский район": {
        "slug": "tevrizskij-r52",
        "administration": "Администрация Тевризского муниципального района Омской области",
    },
    "Тюкалинский район": {
        "slug": "tyukalinskij-r52",
        "administration": "Администрация Тюкалинского муниципального района Омской области",
    },
    "Усть-Ишимский район": {
        "slug": "ust-ishimskij-r52",
        "administration": "Администрация Усть-Ишимского муниципального района Омской области",
    },
    "Черлакский район": {
        "slug": "cherlakskij-r52",
        "administration": "Администрация Черлакского муниципального района Омской области",
    },
    "Шербакульский район": {
        "slug": "sherbakulskij-r52",
        "administration": "Администрация Шербакульского муниципального района Омской области",
    },
    "Омск г.о.": {
        "host": "admomsk.gosuslugi.ru",
        "administration": "Администрация города Омска",
    },
}

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(?:\+7|8)[\s\-()]*(?:\d[\s\-()]*){10,}")


def _fetch(url: str) -> str:
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={"User-Agent": "ZeroProblems/1.0 research"})
    with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _extract(html: str) -> dict:
    emails = list(dict.fromkeys(EMAIL_RE.findall(html)))
    phones = list(dict.fromkeys(PHONE_RE.findall(html)))
    # prefer omskportal / admomsk emails
    preferred = [e for e in emails if "omskportal" in e or "admomsk" in e]
    email = preferred[0] if preferred else (emails[0] if emails else "")
    phone = phones[0] if phones else ""
    return {"email": email, "phone": phone, "all_emails": emails[:5]}


def main() -> None:
    results: dict[str, dict] = {}
    for name, meta in MUNICIPALITY_SITES.items():
        slug = meta.get("slug")
        host = meta.get("host") or f"{slug}.gosweb.gosuslugi.ru"
        website = f"https://{host}/"
        entry: dict = {
            "administration": meta["administration"],
            "website": website,
            "email": "",
            "phone": "",
            "contact_verified": False,
            "source_url": "",
        }
        for path in ("/glavnoe/kontakty/", "/"):
            url = website.rstrip("/") + path
            try:
                html = _fetch(url)
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                entry["fetch_error"] = str(exc)
                continue
            parsed = _extract(html)
            if parsed["email"] or parsed["phone"]:
                entry["email"] = parsed["email"]
                entry["phone"] = parsed["phone"]
                entry["contact_verified"] = bool(parsed["email"])
                entry["source_url"] = url
                break
        results[name] = entry
        status = "OK" if entry.get("email") else "MISS"
        print(f"{status} {name}: {entry.get('email') or entry.get('fetch_error', 'no email')}")

    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
