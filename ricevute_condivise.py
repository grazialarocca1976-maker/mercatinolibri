import os
import re
import datetime
from urllib.parse import quote
import requests
from reportlab.platypus import Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

PROJECT_ID = "ikugmkhbmyohkdbfupnx"
CHIAVE_SUPABASE = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlrdWdta2hibXlvaGtkYmZ1cG54Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODM4NTg3ODYsImV4cCI6MjA5OTQzNDc4Nn0.W0ASwL4tJxwd_ziYXImw0aXdj3RACSGObUd0tjKyN5w"


def _sanifica_testo(valore):
    if valore is None:
        return "sconosciuto"
    testo = re.sub(r"[^a-zA-Z0-9._-]+", "-", str(valore).strip().lower())
    testo = re.sub(r"-+", "-", testo).strip("-")
    return testo or "sconosciuto"


def build_receipt_storage_path(tipo_ricevuta, dati_cliente, data_riferimento=None, suffisso=None):
    data_testo = data_riferimento or datetime.datetime.now().strftime("%Y-%m-%d")
    if isinstance(data_testo, datetime.date):
        data_testo = data_testo.strftime("%Y-%m-%d")
    data_testo = str(data_testo).replace("/", "-")

    if isinstance(dati_cliente, dict):
        nome_cliente = _sanifica_testo(dati_cliente.get("cognome") or dati_cliente.get("nome"))
        codice_cliente = _sanifica_testo(dati_cliente.get("codice_personale"))
    else:
        nome_cliente = _sanifica_testo(dati_cliente)
        codice_cliente = ""

    parti = [tipo_ricevuta, data_testo]
    if codice_cliente:
        parti.append(codice_cliente)
    elif nome_cliente:
        parti.append(nome_cliente)
    if suffisso:
        parti.append(_sanifica_testo(suffisso))
    return "-".join(parti) + ".pdf"


def build_public_storage_url(project_id, bucket_name, object_path):
    return f"https://{project_id}.supabase.co/storage/v1/object/public/{bucket_name}/{quote(object_path, safe='/')}"


def upload_pdf_to_supabase_storage(pdf_bytes, object_path, bucket_name="ricevute", project_id=None, api_key=None):
    if not pdf_bytes:
        return {"ok": False, "url": None, "error": "Nessun PDF da caricare."}

    project_id = project_id or PROJECT_ID
    api_key = api_key or CHIAVE_SUPABASE
    url = f"https://{project_id}.supabase.co/storage/v1/object/{bucket_name}/{object_path}"
    headers = {
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/pdf",
        "x-upsert": "true",
    }

    try:
        response = requests.post(url, headers=headers, data=pdf_bytes, params={"upsert": "true"}, timeout=30)
    except requests.RequestException as exc:
        return {"ok": False, "url": None, "error": str(exc)}

    if response.status_code < 400:
        return {"ok": True, "url": build_public_storage_url(project_id, bucket_name, object_path), "error": None}
    return {"ok": False, "url": None, "error": response.text or f"Errore upload ({response.status_code})"}


def pubblica_ricevuta_online(st, pdf_bytes, tipo_ricevuta, dati_cliente, data_riferimento=None, suffisso=None):
    nome_file = build_receipt_storage_path(tipo_ricevuta, dati_cliente, data_riferimento=data_riferimento, suffisso=suffisso)
    risultato = upload_pdf_to_supabase_storage(pdf_bytes, nome_file)

    if risultato["ok"]:
        st.session_state["ultima_ricevuta_url"] = risultato["url"]
        st.success("📤 Ricevuta caricata online e disponibile da remoto.")
        st.link_button("🔗 Apri ricevuta online", risultato["url"], use_container_width=True)
    else:
        st.caption(f"⚠️ Upload online non disponibile: {risultato.get('error', 'errore sconosciuto')}")
    return risultato


def list_receipts(bucket_name="ricevute", project_id=None, api_key=None, limit=100, prefix=None):
    """List objects in the Supabase Storage bucket."""
    project_id = project_id or PROJECT_ID
    api_key = api_key or CHIAVE_SUPABASE
    url = f"https://{project_id}.supabase.co/storage/v1/object/list/{bucket_name}"
    headers = {"apikey": api_key, "Authorization": f"Bearer {api_key}"}
    payload = {"limit": limit, "prefix": prefix or ""}
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=20)
    except requests.RequestException as exc:
        return {"ok": False, "error": str(exc), "objects": []}
    if r.status_code >= 400:
        return {"ok": False, "error": r.text or f"Status {r.status_code}", "objects": []}
    try:
        objs = r.json()
    except Exception:
        return {"ok": False, "error": "Invalid JSON from storage list", "objects": []}
    return {"ok": True, "objects": objs}

def inserisci_intestazione_marconi(story):
    styles = getSampleStyleSheet()
    nome_logo = "logo-marconi.png"
    stile_contatti = ParagraphStyle('ContattiMinimi', parent=styles['Normal'], fontSize=8, leading=10, textColor=colors.HexColor("#555555"))
    info_aziendali = "<b>MERCATINO LIBRI MARCONI VERONA</b><br/>Email: info@librimarconiverona.it | Tel: 379 3121496"
    
    if os.path.exists(nome_logo):
        try:
            story.append(Image(nome_logo, width=130, height=50))
            story.append(Spacer(1, 5))
            story.append(Paragraph(info_aziendali, stile_contatti))
            story.append(Spacer(1, 15))
        except:
            story.append(Paragraph("<b>📚 MERCATINO LIBRI MARCONI</b>", styles['Heading2']))
            story.append(Paragraph(info_aziendali, stile_contatti))
            story.append(Spacer(1, 15))
    else:
        story.append(Paragraph("<b>📚 MERCATINO LIBRI MARCONI</b>", styles['Heading2']))
        story.append(Paragraph(info_aziendali, stile_contatti))
        story.append(Spacer(1, 15))

def inserisci_anagrafica_cliente(story, ruolo_testo, dati_c):
    styles = getSampleStyleSheet()
    stile_ruolo = ParagraphStyle('RuoloTitolo', parent=styles['Normal'], fontSize=10, fontName='Helvetica-Bold', textColor=colors.HexColor("#333333"))
    stile_dati = ParagraphStyle('DatiCliente', parent=styles['Normal'], fontSize=9, leading=14, textColor=colors.HexColor("#222222"))
    
    nome = dati_c.get('nome', '').upper()
    cognome = dati_c.get('cognome', '').upper()
    codice = dati_c.get('codice_personale', '').upper()
    tel = dati_c.get('telefono', '') if dati_c.get('telefono') else 'N.D.'
    email = dati_c.get('email', '').strip() if dati_c.get('email') else 'N.D.'
    
    p_ruolo = Paragraph(f"<b>{ruolo_testo}</b>", stile_ruolo)
    p_nominativo = Paragraph(f"<b>Nominativo:</b> {cognome} {nome}", stile_dati)
    p_codice = Paragraph(f"<b>Codice Cliente:</b> {codice}", stile_dati)
    p_telefono = Paragraph(f"📞 <b>Tel:</b> {tel}", stile_dati)
    p_email = Paragraph(f"✉️ <b>Email:</b> {email}", stile_dati)
    
    dati_impaginati = [
        [p_ruolo, ""],
        [p_nominativo, p_telefono],
        [p_codice, p_email]
    ]
    
    tabella_pulita = Table(dati_impaginati, colWidths=[270, 270])
    tabella_pulita.setStyle(TableStyle([
        ('SPAN', (0,0), (1,0)),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,1), (-1,-1), 2),
        ('BOTTOMPADDING', (0,1), (-1,-1), 4),
        ('LINEBELOW', (0,0), (1,0), 0.8, colors.HexColor("#333333")),
        ('LINEBELOW', (0,-1), (1,-1), 0.5, colors.HexColor("#cccccc")),
    ]))
    story.append(tabella_pulita)
    story.append(Spacer(1, 15))

def inserisci_clausole_legali_ritiro(story):
    styles = getSampleStyleSheet()
    stile_legale = ParagraphStyle('NoteLegaliDelega', parent=styles['Normal'], fontSize=7, leading=9, textColor=colors.HexColor("#444444"))
    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>📝 MODULO DI DELEGA ALLA LIQUIDAZIONE / RITIRO INSOLUTO</b>", styles['Heading4']))
    story.append(Spacer(1, 4))
    testo_delega = (
        "Il sottoscritto DELEGA il sig./sig.ra _____________________________________ (Documento ID: _____________________) "
        "a effettuare per proprio conto le operazioni di riscossione dei crediti o di ritiro dei volumi rimasti invenduti al "
        "termine dell'anno scolastico. <br/><br/>"
        "Firma del Delegante: ____________________________________    Firma del Delegato: ____________________________________"
    )
    story.append(Paragraph(testo_delega, stile_legale))

def inserisci_qrcode_marconi(story):
    styles = getSampleStyleSheet()
    stile_privacy = ParagraphStyle('NoteLegaliPrivacy', parent=styles['Normal'], fontSize=7, leading=9, textColor=colors.HexColor("#444444"))
    story.append(Spacer(1, 15))
    story.append(Paragraph("<b>📄 INFORMATIVA PRIVACY (GDPR UE 2016/679)</b>", styles['Heading4']))
    story.append(Spacer(1, 4))
    testo_privacy = (
        "Si dichiara di aver preso visione delle condizioni del servizio e si autorizza il trattamento dei dati personali "
        "ai sensi del Regolamento UE 2016/679 (GDPR). I dati verranno trattati in modo digitale ed esclusivamente "
        "per le finalità amministrative, contabili e di tracciamento dei libri legati al Mercatino Marconi Verona."
    )
    story.append(Paragraph(testo_privacy, stile_privacy))
    nome_qr = "qr_download.png"
    if os.path.exists(nome_qr):
        try:
            story.append(Spacer(1, 15))
            story.append(Paragraph("<b>Scansiona il QRCode per accedere ai servizi online:</b>", styles['Normal']))
            story.append(Spacer(1, 5))
            story.append(Image(nome_qr, width=70, height=70))
        except:
            pass