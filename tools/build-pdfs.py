"""Erzeugt die PDF-Versionen des Lebenslaufs (DE und EN) aus index.html.

Nach JEDER inhaltlichen Änderung an index.html ausführen und die PDFs mitcommitten:
    python3 tools/build-pdfs.py

Benötigt: Python mit playwright (Chromium) und pypdf.
Prüft, dass jede Sprache genau 2 A4-Seiten ergibt, sonst Abbruch.
"""
import functools
import http.server
import pathlib
import sys
import threading

from playwright.sync_api import sync_playwright
from pypdf import PdfReader, PdfWriter

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "pdf"
TARGETS = {
    "de": ("", "Lebenslauf_Severin_Strebel.pdf", "Lebenslauf – Severin Strebel"),
    "en": ("?lang=en", "CV_Severin_Strebel_EN.pdf", "CV – Severin Strebel"),
}


def serve():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    handler = functools.partial(Quiet, directory=str(ROOT))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def main():
    OUT.mkdir(exist_ok=True)
    srv = serve()
    base = f"http://127.0.0.1:{srv.server_address[1]}/"
    ok = True
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for lang, (query, name, title) in TARGETS.items():
            page = browser.new_page(viewport={"width": 1200, "height": 1600})
            page.goto(base + query, wait_until="networkidle")
            page.evaluate("document.fonts.ready")
            page.evaluate("window.dispatchEvent(new Event('beforeprint'))")
            page.wait_for_timeout(300)
            counts = page.evaluate("[...document.querySelectorAll('.count')].map(c => c.textContent === c.dataset.to)")
            if not all(counts):
                sys.exit("FEHLER: Zähler zeigen nicht den Endwert.")
            raw = OUT / (name + ".tmp")
            page.pdf(path=str(raw), prefer_css_page_size=True, print_background=True)
            page.close()

            reader = PdfReader(str(raw))
            writer = PdfWriter(clone_from=reader)
            writer.add_metadata({
                "/Title": title,
                "/Author": "Severin Strebel",
                "/Subject": "Lebenslauf" if lang == "de" else "Curriculum vitae",
                "/Creator": "severin-strebel.ch",
                "/Producer": "severin-strebel.ch",
            })
            with open(OUT / name, "wb") as fh:
                writer.write(fh)
            raw.unlink()
            pages = len(reader.pages)
            print(f"{lang}: pdf/{name} – {pages} Seiten, {(OUT / name).stat().st_size // 1024} KB")
            if pages != 2:
                ok = False
        browser.close()
    srv.shutdown()
    if not ok:
        sys.exit("FEHLER: Eine Sprache ergibt nicht genau 2 Seiten.")


if __name__ == "__main__":
    main()
