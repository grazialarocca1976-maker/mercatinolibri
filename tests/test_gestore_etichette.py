import unittest

from gestore_etichette import prepara_dati_etichette


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


if __name__ == "__main__":
    unittest.main()
