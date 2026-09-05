import xml.etree.ElementTree as ET

from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator


SOURCE_URL = "https://www.eczacibasiilac.com.tr/news"
BASE_URL = "https://www.eczacibasiilac.com.tr"
OUTPUT_FILE = Path("docs/feed.xml")
MAX_ITEMS = 80

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/130.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def limpiar(texto):
    return " ".join((texto or "").split())


def leer_anteriores():
    anteriores = {}

    if not OUTPUT_FILE.exists():
        return anteriores

    try:
        root = ET.parse(OUTPUT_FILE).getroot()

        for item in root.findall("./channel/item"):
            enlace = limpiar(item.findtext("link"))

            if enlace:
                anteriores[enlace] = {
                    "title": limpiar(item.findtext("title")),
                    "description": limpiar(
                        item.findtext("description")
                    ),
                    "pubDate": limpiar(item.findtext("pubDate")),
                }

    except Exception as error:
        print(f"No se pudo leer la RSS anterior: {error}")

    return anteriores


def obtener_noticias():
    respuesta = requests.get(
        SOURCE_URL,
        headers=HEADERS,
        timeout=60
    )
    respuesta.raise_for_status()

    soup = BeautifulSoup(respuesta.text, "html.parser")
    anteriores = leer_anteriores()
    noticias = {}

    for tarjeta in soup.select(".news-item"):
        enlace_elemento = tarjeta.select_one(
            'a[href*="/news/"]'
        )
        titulo_elemento = tarjeta.select_one(
            ".news-item-description p"
        )

        if not enlace_elemento or not titulo_elemento:
            continue

        href = enlace_elemento.get("href", "")
        titulo = limpiar(
            titulo_elemento.get_text(" ", strip=True)
        )

        if not href or not titulo:
            continue

        enlace = urljoin(BASE_URL, href)
        enlace = enlace.split("?")[0].split("#")[0]

        # Evitar enlaces que no sean noticias.
        if "/news/" not in enlace:
            continue

        if enlace in noticias:
            continue

        if enlace in anteriores:
            fecha = anteriores[enlace]["pubDate"]
        else:
            fecha = datetime.now(timezone.utc)

        noticias[enlace] = {
            "title": titulo,
            "link": enlace,
            "description": (
                "Noticia publicada por "
                "Eczacıbaşı Pharmaceuticals Marketing."
            ),
            "date": fecha,
        }

    if not noticias:
        raise RuntimeError(
            "No se encontraron noticias. "
            "La RSS anterior no será eliminada."
        )

    return noticias, anteriores


def generar_rss():
    noticias, anteriores = obtener_noticias()

    for enlace, anterior in anteriores.items():
        if enlace not in noticias:
            noticias[enlace] = {
                "title": anterior["title"],
                "link": enlace,
                "description": anterior["description"],
                "date": anterior["pubDate"],
            }

    elementos = list(noticias.values())[:MAX_ITEMS]

    feed = FeedGenerator()
    feed.title("Eczacıbaşı Pharmaceuticals - News")
    feed.link(href=SOURCE_URL, rel="alternate")
    feed.description(
        "Últimas noticias de Eczacıbaşı Pharmaceuticals Marketing"
    )
    feed.language("en")
    feed.id(SOURCE_URL)
    feed.lastBuildDate(datetime.now(timezone.utc))

    for noticia in reversed(elementos):
        entrada = feed.add_entry()
        entrada.id(noticia["link"])
        entrada.title(noticia["title"])
        entrada.link(href=noticia["link"])
        entrada.description(noticia["description"])

        fecha = noticia["date"]

        if isinstance(fecha, str):
            try:
                from email.utils import parsedate_to_datetime
                fecha = parsedate_to_datetime(fecha)
            except Exception:
                fecha = datetime.now(timezone.utc)

        entrada.pubDate(fecha)

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    feed.rss_file(
        str(OUTPUT_FILE),
        pretty=True
    )

    print(f"RSS creada con {len(elementos)} noticias.")


if __name__ == "__main__":
    generar_rss()
