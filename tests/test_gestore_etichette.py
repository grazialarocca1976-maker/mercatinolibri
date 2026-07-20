import unittest

from gestore_etichette import (
    prepara_dati_etichette,
    genera_preview_etichette,
    genera_griglia_a4_bytes,
    stampa_etichette_tm_l90,
)


class TestGestoreEtichette(unittest.TestCase):
    def test_prepara_dati_etichette_da_payload_ritiro(self):
        payload = [
            {"id_libro": 12, "titolo": "Il titolo A"},
            {"id": 15, "titolo": "Il titolo B"},
        ]

        risultato = prepara_dati_etichette(payload)

        self.assertEqual(risultato[0]["id"], "12")
        self.assertEqual(risultato[0]["titolo"], "Il titolo A")
        self.assertEqual(risultato[1]["id"], "15")
        self.assertEqual(risultato[1]["titolo"], "Il titolo B")

    def test_prepara_dati_etichette_da_etichetta(self):
        payload = [
            {"etichetta": "27 - ABC", "titolo": "Il titolo C"},
        ]

        risultato = prepara_dati_etichette(payload)

        self.assertEqual(risultato[0]["id"], "27")
        self.assertEqual(risultato[0]["titolo"], "Il titolo C")

    def test_prepara_dati_etichette_con_barcode_persona_libro(self):
        payload = [
            {"id_libro": 42, "codice_personale": "AB12", "titolo": "Il titolo D"},
        ]

        risultato = prepara_dati_etichette(payload)

        self.assertEqual(risultato[0]["barcode"], "AB12-42")

    def test_prepara_dati_etichette_includi_fascicoli(self):
        payload = [
            {
                "id_libro": 12,
                "titolo": "Matematica",
                "prevede_fascicoli": True,
                "totale_fascicoli": 3,
                "fascicoli_consegnati": 2,
            },
            {
                "id_libro": 15,
                "titolo": "Fisica",
                "prevede_fascicoli": False,
            },
        ]

        risultato = prepara_dati_etichette(payload)

        self.assertTrue(risultato[0]["prevede_fascicoli"])
        self.assertEqual(risultato[0]["totale_fascicoli"], 3)
        self.assertEqual(risultato[0]["fascicoli_consegnati"], 2)
        self.assertFalse(risultato[1]["prevede_fascicoli"])
        self.assertEqual(risultato[1]["totale_fascicoli"], 0)
        self.assertEqual(risultato[1]["fascicoli_consegnati"], 0)

    def test_genera_preview_etichette_mostra_fascicoli(self):
        payload = [
            {
                "id_libro": 12,
                "titolo": "Matematica",
                "barcode": "1-12",
                "prevede_fascicoli": True,
                "totale_fascicoli": 3,
                "fascicoli_consegnati": 2,
            },
        ]

        righe = genera_preview_etichette(payload)

        self.assertEqual(len(righe), 1)
        self.assertIn("FASC: 2/3", righe[0])

    def test_genera_griglia_a4_bytes_con_fascicoli(self):
        payload = [
            {
                "id_libro": 12,
                "titolo": "Matematica",
                "barcode": "1-12",
                "prevede_fascicoli": True,
                "totale_fascicoli": 3,
                "fascicoli_consegnati": 2,
            },
        ]

        pdf = genera_griglia_a4_bytes(payload)

        self.assertIsNotNone(pdf)
        self.assertTrue(pdf.startswith(b"%PDF"))

    def test_stampa_tm_l90_passaggio_fascicoli(self):
        captured = []

        class FakePrinter:
            def __init__(self, *a, **k):
                captured.append(self)
                self.texts = []

            def text(self, t):
                self.texts.append(t)

            def barcode(self, *a, **k):
                pass

            def cut(self):
                pass

        import gestore_etichette as ge

        original = ge.Usb
        ge.Usb = lambda *a, **k: FakePrinter()
        try:
            payload = [
                {
                    "id_libro": 12,
                    "titolo": "Matematica",
                    "barcode": "1-12",
                    "prevede_fascicoli": True,
                    "totale_fascicoli": 3,
                    "fascicoli_consegnati": 2,
                },
            ]
            esito = stampa_etichette_tm_l90(payload)
            self.assertTrue(esito)
            self.assertTrue(len(captured) > 0)
            all_text = "\n".join(captured[0].texts)
            self.assertIn("Fascicoli: 2/3", all_text)
        finally:
            ge.Usb = original


if __name__ == "__main__":
    unittest.main()