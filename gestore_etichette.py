import importlib
import os
import tempfile
import math
from pathlib import Path

Usb = None
try:
    escpos_printer = importlib.import_module("escpos.printer")
    Usb = getattr(escpos_printer, "Usb", None)
except Exception:  # pragma: no cover - fallback per ambienti senza escpos
    Usb = None

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.graphics.barcode import code128
from io import BytesIO


def prepara_dati_etichette(lista_libri):
    """Normalizza una lista di libri proveniente dal ritiro o dalla cassa."""
    etichette = []
    for libro in lista_libri or []:
        if not isinstance(libro, dict):
            continue

        id_val = libro.get("id_libro")
        if id_val is None:
            id_val = libro.get("id")
        if id_val is None:
                etichetta = libro.get("etichetta") or ""
                if etichetta:
                    parti = [p.strip() for p in str(etichetta).split("-") if p.strip()]
                    parti_numeriche = [p for p in parti if p.isdigit()]
                    if parti_numeriche:
                        id_val = int(parti_numeriche[-1])
        if id_val is None:
            continue

        titolo = libro.get("titolo") or libro.get("nome") or ""
        barcode_value = libro.get("barcode")
        if barcode_value is None:
            # Il barcode per scansione rapida usa solo id_venditore-id_libro (numerico)
            id_vend = libro.get("id_venditore") or libro.get("client_id") or ""
            if id_vend:
                barcode_value = f"{id_vend}-{id_val}"
            else:
                barcode_value = str(id_val)



        etichette.append({
            "id": str(id_val),
            "titolo": str(titolo).strip(),
            "barcode": str(barcode_value),
            "prevede_fascicoli": bool(libro.get("prevede_fascicoli", False)),
            "totale_fascicoli": int(libro.get("totale_fascicoli", 0) or 0),
            "fascicoli_consegnati": int(libro.get("fascicoli_consegnati", 0) or 0),
            "codice_personale": libro.get("codice_personale") or libro.get("persona") or libro.get("cliente") or "",
            "volume": libro.get("volume") or libro.get("classi") or "",
        })

    return etichette


# =========================================================================
# 🖨️ MODALITÀ 1: STAMPA SINGOLA SU EPSON TM-L90 (Rotolo Termico / Etichette)
# =========================================================================
def stampa_singola_tml90(id_libro, titolo, barcode_value=None, fascicoli=None):
    """Invia direttamente alla stampante termica un'etichetta singola con barcode."""
    if Usb is None:
        print("Modulo escpos non disponibile. Impossibile inviare alla TM-L90.")
        return False

    try:
        p = Usb(0x04b8, 0x0202)
        p.text("MARCONI VERONA - MERCATINO\n")
        p.text(f"Libro: {titolo[:22]}\n")
        p.text("------------------------\n")
        if fascicoli:
            p.text(f"Fascicoli: {fascicoli}\n")

        barcode_da_stampare = str(barcode_value or id_libro)
        p.text(f"{barcode_da_stampare}\n")
        p.barcode(barcode_da_stampare, 'CODE39', width=3, height=70, pos='BELOW', font='A')
        p.cut()
        return True
    except Exception as e:
        print(f"Errore hardware TM-L90: {e}")
        return False


def stampa_etichette_tm_l90(lista_libri):
    """Stampa una etichetta per ogni libro sulla TM-L90."""
    etichette = prepara_dati_etichette(lista_libri)
    if not etichette:
        return False

    for etichetta in etichette:
        fascicoli_str = None
        if etichetta.get("prevede_fascicoli"):
            fascicoli_str = f"{etichetta.get('fascicoli_consegnati', 0)}/{etichetta.get('totale_fascicoli', 0)}"
        if not stampa_singola_tml90(etichetta['id'], etichetta['titolo'], etichetta.get('barcode'), fascicoli_str):
            return False
    return True


def calcola_layout_personalizzato(larghezza_foglio_mm, altezza_foglio_mm, totale_etichette):
    """Calcola colonne, righe e dimensioni etichetta a partire dal foglio e dal totale.
    Le dimensioni del font e del barcode vengono poi scalate in proporzione."""
    if totale_etichette is None or totale_etichette <= 0:
        totale_etichette = 1
    larghezza_foglio_mm = float(larghezza_foglio_mm or 210)
    altezza_foglio_mm = float(altezza_foglio_mm or 297)

    # Stima un numero di colonne che mantenga un rapporto d'aspetto simile a 70x36
    rapporto = larghezza_foglio_mm / altezza_foglio_mm
    colonne = max(1, round(math.sqrt(totale_etichette * rapporto)))
    righe = max(1, math.ceil(totale_etichette / colonne))
    while colonne * righe < totale_etichette:
        righe += 1

    larghezza_etichetta = larghezza_foglio_mm / colonne
    altezza_etichetta = altezza_foglio_mm / righe
    scala = altezza_etichetta / 36.0  # riferimento: etichetta da 36mm

    return {
        "larghezza_etichetta_mm": larghezza_etichetta,
        "altezza_etichetta_mm": altezza_etichetta,
        "margine_sinistro_mm": 0,
        "margine_superiore_mm": 0,
        "colonne": colonne,
        "righe": righe,
        "scala": scala,
    }


def _disegna_etichetta_a4(c, x, y, w, h, libro, scala=1.0):
    """Disegna un'etichetta A4 adesiva ben spaziata e leggibile (niente sovrapposizioni).
    Disposizione come da immagine:
    - MARCONI VERONA (in alto a sinistra, Helvetica-Bold)
    - TITOLO (sotto, Helvetica)
    - Codice a barre (grande, centrato)
    - ID: {id} {barcode_value} (sulla stessa riga in basso, Helvetica-Bold)
    """
    s = max(0.6, float(scala))
    titolo = str(libro.get("titolo", "")).upper()[:28]
    barcode_value = str(libro.get("barcode", libro.get("id", "")))
    id_libro = libro.get("id", "")

    # Calcolo coordinate verticali relative per mantenere proporzioni con la scala
    # y è l'angolo inferiore sinistro dell'etichetta, h è l'altezza
    title_y = y + h - 5 * mm * s
    subtitle_y = y + h - 10 * mm * s
    
    # Il barcode vive al centro verticale
    barcode_h = min(15 * mm * s, h - 22 * mm * s)
    if barcode_h < 6 * mm:
        barcode_h = 6 * mm
    barcode_y = y + 6 * mm * s
    
    # ID e Codice sulla stessa riga in basso
    id_y = y + 2 * mm * s

    # 1. Intestazione: MARCONI VERONA in Bold
    c.setFont("Helvetica-Bold", max(7, 12 * s))
    c.drawString(x + 4 * mm * s, title_y, "MARCONI VERONA")

    # 2. Titolo sotto l'intestazione
    c.setFont("Helvetica", max(6, 10 * s))
    c.drawString(x + 4 * mm * s, subtitle_y, titolo)
    
    # 2b. Volume / Classe sotto il titolo (più piccolo)
    volume = str(libro.get("volume", "") or "")
    if volume and volume.lower() != "nan":
        c.setFont("Helvetica", max(5, 8 * s))
        c.drawString(x + 4 * mm * s, subtitle_y - 3.5 * mm * s, f"Vol. {volume}")


    # Se ci sono fascicoli, mostriamo una nota ben visibile in rosso sotto il titolo
    if libro.get("prevede_fascicoli"):
        c.setFillColorRGB(0.8, 0, 0)  # Rosso scuro
        c.setFont("Helvetica-Bold", max(7, 11 * s))
        c.drawString(
            x + 4 * mm * s,
            subtitle_y - 4 * mm * s,
            f"FASCICOLI: {libro.get('fascicoli_consegnati', 0)}/{libro.get('totale_fascicoli', 0)}",
        )
        c.setFillColorRGB(0, 0, 0)  # Torna a nero


    # 3. Codice a barre grande
    barcode = code128.Code128(barcode_value, barWidth=max(0.2 * mm, 0.4 * mm * s), barHeight=barcode_h)
    barcode.drawOn(c, x + 4 * mm * s, barcode_y)

    # 4. Codice completo (persona-id) in basso
    codice_completo = libro.get("codice_personale", "")
    if codice_completo:
        codice_completo = f"{codice_completo}-{id_libro}"
    else:
        codice_completo = barcode_value
    c.setFont("Helvetica-Bold", max(6, 10 * s))
    c.drawString(x + 4 * mm * s, id_y, codice_completo)



def _normalizza_layout(layout):
    """Restituisce un layout dict completo (con scala) a partire da None/str/dict."""
    if layout is None:
        layout = {
            "larghezza_etichetta_mm": 70,
            "altezza_etichetta_mm": 36,
            "margine_sinistro_mm": 0,
            "margine_superiore_mm": 11,
            "colonne": 3,
            "righe": 8,
        }
    elif isinstance(layout, str):
        if layout.lower() == "a5":
            layout = {"larghezza_etichetta_mm": 90, "altezza_etichetta_mm": 50, "margine_sinistro_mm": 5, "margine_superiore_mm": 10, "colonne": 2, "righe": 4}
        elif layout.lower() == "10":
            layout = {"larghezza_etichetta_mm": 70, "altezza_etichetta_mm": 36, "margine_sinistro_mm": 0, "margine_superiore_mm": 11, "colonne": 2, "righe": 5}
        else:
            layout = {"larghezza_etichetta_mm": 70, "altezza_etichetta_mm": 36, "margine_sinistro_mm": 0, "margine_superiore_mm": 11, "colonne": 3, "righe": 8}
    elif isinstance(layout, dict):
        # Layout personalizzato: foglio + totale etichette -> calcolo automatico
        if "larghezza_foglio_mm" in layout and "totale_etichette" in layout:
            layout = calcola_layout_personalizzato(
                layout.get("larghezza_foglio_mm", 210),
                layout.get("altezza_foglio_mm", 297),
                layout.get("totale_etichette", 1),
            )
    return layout


def genera_griglia_a4_bytes(lista_libri, layout=None, start_index=0):
    """Genera un PDF in memoria (bytes) per download invece di scrivere sul file system.
    Supporta start_index per saltare le prime etichette già usate sul foglio."""
    libri_normalizzati = prepara_dati_etichette(lista_libri)
    if not libri_normalizzati:
        return None

    layout = _normalizza_layout(layout)

    LARGHEZZA_ETICHETTA = layout.get("larghezza_etichetta_mm", 70) * mm
    ALTEZZA_ETICHETTA = layout.get("altezza_etichetta_mm", 36) * mm
    MARGIN_LEFT = layout.get("margine_sinistro_mm", 0) * mm
    MARGIN_TOP = layout.get("margine_superiore_mm", 11) * mm
    COLONNE = layout.get("colonne", 3)
    RIGHE = layout.get("righe", 8)
    SCALA = layout.get("scala", ALTEZZA_ETICHETTA / (36 * mm))

    buffer = BytesIO()
    try:
        c = canvas.Canvas(buffer, pagesize=A4)
        largheza_pagina, altezza_pagina = A4

        colonna_attuale = start_index % COLONNE
        riga_attuale = (start_index // COLONNE) % RIGHE

        for libro in libri_normalizzati:
            x = MARGIN_LEFT + (colonna_attuale * LARGHEZZA_ETICHETTA)
            y = altezza_pagina - MARGIN_TOP - ((riga_attuale + 1) * ALTEZZA_ETICHETTA)

            _disegna_etichetta_a4(c, x, y, LARGHEZZA_ETICHETTA, ALTEZZA_ETICHETTA, libro, SCALA)

            colonna_attuale += 1
            if colonna_attuale >= COLONNE:
                colonna_attuale = 0
                riga_attuale += 1

            if riga_attuale >= RIGHE:
                c.showPage()
                colonna_attuale = 0
                riga_attuale = 0

        c.save()
        buffer.seek(0)
        return buffer.getvalue()
    except Exception as e:
        print(f"Errore generazione PDF etichette A4 (bytes): {e}")
        return None


# =========================================================================
# 📄 MODALITÀ 2: STAMPA MASSIVA SU FOGLIO A4 PRETAGLIATO (Griglia 3x8)
# =========================================================================
def genera_preview_etichette(lista_libri):
    """Restituisce una stringa leggibile da mostrare in anteprima a schermo."""
    etichette = prepara_dati_etichette(lista_libri)
    if not etichette:
        return []

    righe = []
    for etichetta in etichette:
        riga = f"{etichetta['id']} | {etichetta['titolo'][:28]} | {etichetta['barcode']}"
        if etichetta.get("prevede_fascicoli"):
            riga += f" | FASC: {etichetta.get('fascicoli_consegnati', 0)}/{etichetta.get('totale_fascicoli', 0)}"
        righe.append(riga)
    return righe


def genera_griglia_a4(lista_libri, file_output="etichette_a4_marconi.pdf", stampa=True, layout=None, start_index=0):
    """Genera un PDF formattato al millimetro per fogli A4 adesivi. Supporta layout standard, personalizzati e start_index."""
    libri_normalizzati = prepara_dati_etichette(lista_libri)
    if not libri_normalizzati:
        return False

    base_dir = Path(__file__).resolve().parent
    output_path = Path(file_output) if os.path.isabs(file_output) else base_dir / file_output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    candidate_paths = [output_path]
    temp_dir = Path(tempfile.gettempdir())
    candidate_paths.append(temp_dir / f"etichette_a4_marconi_{os.getpid()}.pdf")

    layout = _normalizza_layout(layout)

    LARGHEZZA_ETICHETTA = layout.get("larghezza_etichetta_mm", 70) * mm
    ALTEZZA_ETICHETTA = layout.get("altezza_etichetta_mm", 36) * mm
    MARGIN_LEFT = layout.get("margine_sinistro_mm", 0) * mm
    MARGIN_TOP = layout.get("margine_superiore_mm", 11) * mm
    COLONNE = layout.get("colonne", 3)
    RIGHE = layout.get("righe", 8)
    SCALA = layout.get("scala", ALTEZZA_ETICHETTA / (36 * mm))

    output_file = None
    for candidate in candidate_paths:
        try:
            c = canvas.Canvas(str(candidate), pagesize=A4)
            largheza_pagina, altezza_pagina = A4

            colonna_attuale = start_index % COLONNE
            riga_attuale = (start_index // COLONNE) % RIGHE

            for libro in libri_normalizzati:
                x = MARGIN_LEFT + (colonna_attuale * LARGHEZZA_ETICHETTA)
                y = altezza_pagina - MARGIN_TOP - ((riga_attuale + 1) * ALTEZZA_ETICHETTA)

                _disegna_etichetta_a4(c, x, y, LARGHEZZA_ETICHETTA, ALTEZZA_ETICHETTA, libro, SCALA)

                colonna_attuale += 1
                if colonna_attuale >= COLONNE:
                    colonna_attuale = 0
                    riga_attuale += 1

                if riga_attuale >= RIGHE:
                    c.showPage()
                    colonna_attuale = 0
                    riga_attuale = 0

            c.save()
            output_file = candidate
            break
        except PermissionError:
            continue
        except Exception as e:
            print(f"Errore generazione PDF etichette A4: {e}")
            return False

    if output_file is None:
        return False

    if stampa:
        try:
            if hasattr(os, "startfile"):
                os.startfile(str(output_file), "print")
            else:
                print("Stampa automatica A4 non disponibile in questo ambiente.")
            return True
        except Exception as e:
            print(f"PDF creato ma stampa automatica A4 non riuscita: {e}")
            return True

    return True