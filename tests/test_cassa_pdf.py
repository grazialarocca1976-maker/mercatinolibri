import unittest

from cassa import genera_pdf_vendita_multipla, genera_pdf_chiusura_giornaliera


class TestCassaPdf(unittest.TestCase):
    def test_genera_pdf_vendita_multipla(self):
        acquirente = {
            "id": 1,
            "nome": "Mario",
            "cognome": "Rossi",
            "codice_personale": "ROS12AB0001",
            "telefono": "3331234567",
            "email": "mario@test.it",
        }
        libri = [
            {"id_libro": 10, "titolo": "Matematica", "prezzo_v": 5.0, "codice_venditore": "ROS12AB"},
            {"id_libro": 11, "titolo": "Italiano", "prezzo_v": 4.5, "codice_venditore": "VER99XY"},
        ]
        pdf = genera_pdf_vendita_multipla(acquirente, libri, 9.5, "Contanti", numero_ricevuta="1/V")
        self.assertIsInstance(pdf, bytes)
        self.assertTrue(pdf.startswith(b"%PDF"))

    def test_genera_pdf_vendita_multipla_numero_none(self):
        acquirente = {"nome": "Mario", "cognome": "Rossi", "codice_personale": "X", "telefono": "", "email": ""}
        libri = [{"id_libro": 1, "titolo": "Libro", "prezzo_v": 1.0, "codice_venditore": "X"}]
        pdf = genera_pdf_vendita_multipla(acquirente, libri, 1.0, "Bancomat")
        self.assertIsInstance(pdf, bytes)
        self.assertTrue(pdf.startswith(b"%PDF"))

    def test_genera_pdf_chiusura_giornaliera(self):
        lista_pezzi = [
            {"id_libro": 10, "titolo": "Matematica", "Prezzo Vendita": 5.0},
            {"id_libro": 11, "titolo": "Italiano", "Prezzo Vendita": 4.5},
        ]
        pdf = genera_pdf_chiusura_giornaliera("19/07/2026", 9.5, 0.0, 9.5, lista_pezzi)
        self.assertIsInstance(pdf, bytes)
        self.assertTrue(pdf.startswith(b"%PDF"))

    def test_genera_pdf_chiusura_giornaliera_vuota(self):
        pdf = genera_pdf_chiusura_giornaliera("19/07/2026", 0.0, 0.0, 0.0, [])
        self.assertIsInstance(pdf, bytes)
        self.assertTrue(pdf.startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()