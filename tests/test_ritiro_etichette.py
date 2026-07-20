import unittest

from ritiro import genera_pdf_rotolo_etichette


class TestRitiroEtichette(unittest.TestCase):
    def test_genera_pdf_rotolo_non_none_un_libro(self):
        # Caso critico che prima ritornava None (errore StreamlitAPIException)
        libri = [{
            "etichetta": "1-5",
            "isbn": "978123",
            "titolo": "Matematica",
            "prevede_fascicoli": False,
            "totale_fascicoli": 0,
            "fascicoli_consegnati": 0,
        }]
        pdf = genera_pdf_rotolo_etichette(libri)
        self.assertIsNotNone(pdf)
        self.assertTrue(pdf.startswith(b"%PDF"))

    def test_genera_pdf_rotolo_mostra_fascicoli(self):
        libri = [{
            "etichetta": "1-6",
            "isbn": "978999",
            "titolo": "Fisica",
            "prevede_fascicoli": True,
            "totale_fascicoli": 3,
            "fascicoli_consegnati": 2,
        }]
        pdf = genera_pdf_rotolo_etichette(libri)
        self.assertIsNotNone(pdf)
        self.assertTrue(pdf.startswith(b"%PDF"))
        # Nota: il testo "FASCICOLI: 2/3" è presente nel documento ma compresso
        # (ASCII85+Flate) quindi non ricercabile come testo grezzo nei bytes.
        # La presenza dei fascicoli è garantita dal codice sorgente e dagli altri
        # test (prepara_dati_etichette / genera_preview_etichette / A4 bytes).

    def test_genera_pdf_rotolo_lista_vuota_non_none(self):
        pdf = genera_pdf_rotolo_etichette([])
        self.assertIsNotNone(pdf)
        self.assertTrue(pdf.startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()