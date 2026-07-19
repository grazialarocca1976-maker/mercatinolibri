import unittest
from unittest.mock import patch

from ricevute_condivise import (
    _sanifica_testo,
    build_receipt_storage_path,
    build_public_storage_url,
)


class TestRicevuteCondivise(unittest.TestCase):
    def test_sanifica_testo_none(self):
        self.assertEqual(_sanifica_testo(None), "sconosciuto")

    def test_sanifica_testo_vuoto(self):
        self.assertEqual(_sanifica_testo("   "), "sconosciuto")

    def test_sanifica_testo_caratteri_speciali(self):
        # Spazi e caratteri non alfanumerici diventano "-"
        self.assertEqual(_sanifica_testo("Mario Rossi"), "mario-rossi")

    def test_sanifica_testo_pulizia_trattini_doppi(self):
        self.assertEqual(_sanifica_testo("a  -  b"), "a-b")

    def test_sanifica_testo_troncamento_estremi(self):
        # I caratteri non alfanumerici (es. #) diventano "-" e vengono troncati agli estremi
        self.assertEqual(_sanifica_testo("##test##"), "test")

    def test_sanifica_testo_mantiene_underscore(self):
        # L'underscore e' un carattere permesso e viene preservato
        self.assertEqual(_sanifica_testo("__test__"), "__test__")

    def test_build_receipt_storage_path_con_dict(self):
        dati = {"cognome": "Rossi", "nome": "Mario", "codice_personale": "ROS12AB0001"}
        nome = build_receipt_storage_path("ritiro", dati, data_riferimento="2026-07-19")
        self.assertTrue(nome.startswith("ritiro-2026-07-19-ros12ab0001"))
        self.assertTrue(nome.endswith(".pdf"))

    def test_build_receipt_storage_path_con_stringa(self):
        nome = build_receipt_storage_path("vendita", "Mario", data_riferimento="2026-07-19")
        self.assertEqual(nome, "vendita-2026-07-19-mario.pdf")

    def test_build_receipt_storage_path_con_suffisso(self):
        dati = {"codice_personale": "ROS12AB0001"}
        nome = build_receipt_storage_path(
            "ritiro", dati, data_riferimento="2026-07-19", suffisso="op-mario-3-libri"
        )
        self.assertEqual(nome, "ritiro-2026-07-19-ros12ab0001-op-mario-3-libri.pdf")

    def test_build_public_storage_url(self):
        url = build_public_storage_url("myproject", "ricevute", "ritiro-2026.pdf")
        self.assertEqual(
            url,
            "https://myproject.supabase.co/storage/v1/object/public/ricevute/ritiro-2026.pdf",
        )


if __name__ == "__main__":
    unittest.main()