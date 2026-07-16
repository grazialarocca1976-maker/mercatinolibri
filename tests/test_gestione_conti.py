import unittest

from gestione_conti import payload_chiusura_conto, payload_storno_vendita


class TestGestioneConti(unittest.TestCase):
    def test_payload_chiusura_conto(self):
        payload = payload_chiusura_conto()
        self.assertEqual(payload["stato"], "chiuso_conto")

    def test_payload_storno_vendita(self):
        payload = payload_storno_vendita()
        self.assertEqual(payload["stato"], "disponibile")
        self.assertIsNone(payload["id_acquirente"])
        self.assertIsNone(payload["metodo_pagamento"])
        self.assertIsNone(payload["data_vendita"])


if __name__ == "__main__":
    unittest.main()
