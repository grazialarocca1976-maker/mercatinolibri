import importlib
import os
import tempfile
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
                    # Formato ufficiale: <codice_personale>-<id_libro> (id_libro alla FINE, numerico)
                    parti = [p.strip() for p in str(etichetta).split("-") if p.strip()]
                    parte_id = parti[-1] if parti else ""
                    if parte_id.isdigit():
                        id_val = int(parte_id)
        if id_val is None:
            continue

        titolo = libro.get("titolo") or libro.get("nome") or ""
        # Prefer explicit barcode if provided
        barcode_value = libro.get("barcode")
        if barcode_value is None:
            # If client numeric id is present, prefer format: <client_id>-<codice_personale>-<id_libro>
            client_id = libro.get("id_venditore") or libro.get("client_id") or libro.get("id_cliente")
            codice_persona = (
                libro.get("codice_personale")
                or libro.get("persona")
                or libro.get("codice_persona")
                or libro.get("cliente")
                or ""
            )
            if client_id and codice_persona:
                barcode_value = f"{client_id}-{codice_persona}-{id_val}"
            elif codice_persona:
                barcode_value = f"{codice_persona}-{id_val}"
            else:
                barcode_value = str(id_val)

        etichette.append({
            "id": str(id_val),
            "titolo": str(titolo).strip(),
            "barcode": str(barcode_value),
        })
    return etichette


# =========================================================================
# 🖨️ MODALITÀ 1: STAMPA SINGOLA SU EPSON TM-L90 (Rotolo Termico / Etichette)
# =========================================================================
def stampa_singola_tml90(id_libro, titolo, barcode_value=None):
    """Invia direttamente alla stampante termica un'etichetta singola con barcode."""
    if Usb is None:
        print("Modulo escpos non disponibile. Impossibile inviare alla TM-L90.")
        return False

    try:
        p = Usb(0x04b8, 0x0202)
        p.text("MARCONI VERONA - MERCATINO\n")
        p.text(f"Libro: {titolo[:22]}\n")
        p.text("------------------------\n")

        barcode_da_stampare = str(barcode_value or id_libro)
        p.text(f"{barcode_da_stampare}\n")
        p.barcode(barcode_da_stampare, 'CODE39', width=2, height=50, pos='BELOW', font='A')
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
        if not stampa_singola_tml90(etichetta['id'], etichetta['titolo'], etichetta.get('barcode')):
            return False
    return True


def genera_griglia_a4_bytes(lista_libri, layout=None, start_index=0):
    """Genera un PDF in memoria (bytes) per download invece di scrivere sul file system.
    Supporta start_index per saltare le prime etichette già usate sul foglio."""
    libri_normalizzati = prepara_dati_etichette(lista_libri)
    if not libri_normalizzati:
        return None

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
            # Layout per 10 etichette: 2 colonne x 5 righe
            layout = {"larghezza_etichetta_mm": 70, "altezza_etichetta_mm": 36, "margine_sinistro_mm": 0, "margine_superiore_mm": 11, "colonne": 2, "righe": 5}
        else:
            layout = {"larghezza_etichetta_mm": 70, "altezza_etichetta_mm": 36, "margine_sinistro_mm": 0, "margine_superiore_mm": 11, "colonne": 3, "righe": 8}

    LARGHEZZA_ETICHETTA = layout.get("larghezza_etichetta_mm", 70) * mm
    ALTEZZA_ETICHETTA = layout.get("altezza_etichetta_mm", 36) * mm
    MARGIN_LEFT = layout.get("margine_sinistro_mm", 0) * mm
    MARGIN_TOP = layout.get("margine_superiore_mm", 11) * mm
    COLONNE = layout.get("colonne", 3)
    RIGHE = layout.get("righe", 8)

    buffer = BytesIO()
    try:
        c = canvas.Canvas(buffer, pagesize=A4)
        largheza_pagina, altezza_pagina = A4

        colonna_attuale = start_index % COLONNE
        riga_attuale = (start_index // COLONNE) % RIGHE

        for libro in libri_normalizzati:
            id_libro = libro['id']
            titolo = libro['titolo'][:20]
            barcode_value = str(libro.get('barcode', id_libro))

            x = MARGIN_LEFT + (colonna_attuale * LARGHEZZA_ETICHETTA)
            y = altezza_pagina - MARGIN_TOP - ((riga_attuale + 1) * ALTEZZA_ETICHETTA)

            # Spaziatura dinamica per evitare sovrapposizioni
            top_padding = 4 * mm
            inner_padding = 2 * mm
            title_y = y + ALTEZZA_ETICHETTA - top_padding
            subtitle_y = title_y - (5 * mm)
            barcode_y = y + (6 * mm)

            c.setFont("Helvetica-Bold", 7)
            c.drawString(x + 4 * mm, title_y, "MARCONI VERONA")
            c.setFont("Helvetica", 7)
            c.drawString(x + 4 * mm, subtitle_y, f"{titolo}")

            barcode = code128.Code128(barcode_value, barWidth=0.25 * mm, barHeight=10 * mm)
            barcode.drawOn(c, x + 4 * mm, barcode_y)

            # ID grande e in grassetto per essere ben visibile
            c.setFont("Helvetica-Bold", 12)
            c.drawString(x + 4 * mm, y + inner_padding + 1 * mm, f"ID: {id_libro}")

            # Codice: la parte finale (es. -31, lo scannable) in grassetto
            parti_codice = str(barcode_value).rsplit("-", 1)
            if len(parti_codice) == 2:
                prefisso, finale = parti_codice
                c.setFont("Helvetica", 7)
                c.drawString(x + 4 * mm, y + 1 * mm, prefisso + "-")
                larg_prefisso = c.stringWidth(prefisso + "-", "Helvetica", 7)
                c.setFont("Helvetica-Bold", 7)
                c.drawString(x + 4 * mm + larg_prefisso, y + 1 * mm, finale)
            else:
                c.setFont("Helvetica-Bold", 7)
                c.drawString(x + 4 * mm, y + 1 * mm, str(barcode_value))

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
        righe.append(f"{etichetta['id']} | {etichetta['titolo'][:28]} | {etichetta['barcode']}")
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
        else:
            layout = {"larghezza_etichetta_mm": 70, "altezza_etichetta_mm": 36, "margine_sinistro_mm": 0, "margine_superiore_mm": 11, "colonne": 3, "righe": 8}

    LARGHEZZA_ETICHETTA = layout.get("larghezza_etichetta_mm", 70) * mm
    ALTEZZA_ETICHETTA = layout.get("altezza_etichetta_mm", 36) * mm
    MARGIN_LEFT = layout.get("margine_sinistro_mm", 0) * mm
    MARGIN_TOP = layout.get("margine_superiore_mm", 11) * mm
    COLONNE = layout.get("colonne", 3)
    RIGHE = layout.get("righe", 8)

    output_file = None
    for candidate in candidate_paths:
        try:
            c = canvas.Canvas(str(candidate), pagesize=A4)
            largheza_pagina, altezza_pagina = A4

            colonna_attuale = start_index % COLONNE
            riga_attuale = (start_index // COLONNE) % RIGHE

            for libro in libri_normalizzati:
                id_libro = libro['id']
                titolo = libro['titolo'][:20]
                barcode_value = str(libro.get('barcode', id_libro))

                x = MARGIN_LEFT + (colonna_attuale * LARGHEZZA_ETICHETTA)
                y = altezza_pagina - MARGIN_TOP - ((riga_attuale + 1) * ALTEZZA_ETICHETTA)

                c.setFont("Helvetica-Bold", 8)
                c.drawString(x + 5 * mm, y + 28 * mm, "MARCONI VERONA")
                c.setFont("Helvetica", 8)
                c.drawString(x + 5 * mm, y + 22 * mm, f"Txt: {titolo}")

                barcode = code128.Code128(barcode_value, barWidth=0.28 * mm, barHeight=12 * mm)
                barcode.drawOn(c, x + 5 * mm, y + 6 * mm)

                # ID grande e in grassetto per essere ben visibile
                c.setFont("Helvetica-Bold", 12)
                c.drawString(x + 5 * mm, y + 2 * mm, f"ID: {id_libro}")

                # Codice: la parte finale (es. -31, lo scannable) in grassetto
                parti_codice = str(barcode_value).rsplit("-", 1)
                if len(parti_codice) == 2:
                    prefisso, finale = parti_codice
                    c.setFont("Helvetica", 7)
                    c.drawString(x + 5 * mm, y + 1 * mm, prefisso + "-")
                    larg_prefisso = c.stringWidth(prefisso + "-", "Helvetica", 7)
                    c.setFont("Helvetica-Bold", 7)
                    c.drawString(x + 5 * mm + larg_prefisso, y + 1 * mm, finale)
                else:
                    c.setFont("Helvetica-Bold", 7)
                    c.drawString(x + 5 * mm, y + 1 * mm, str(barcode_value))

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
