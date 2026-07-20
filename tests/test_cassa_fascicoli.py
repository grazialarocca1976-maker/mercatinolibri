import unittest

from cassa import calcola_prezzo_vendita_scontato


class TestCassaFascicoli(unittest.TestCase):
    def test_senza_sconto(self):
        # (10 - 0) / 2 = 5.0
        self.assertAlmostEqual(calcola_prezzo_vendita_scontato(10.0, 0.0), 5.0)

    def test_con_sconto_4(self):
        # (10 - 4) / 2 = 3.0  -> sconto fascicoli mancanti
        self.assertAlmostEqual(calcola_prezzo_vendita_scontato(10.0, 4.0), 3.0)

    def test_sconto_non_negativo(self):
        # (2 - 4) -> max(0) / 2 = 0.0
        self.assertAlmostEqual(calcola_prezzo_vendita_scontato(2.0, 4.0), 0.0)

    def test_prezzo_base_zero(self):
        self.assertAlmostEqual(calcola_prezzo_vendita_scontato(0.0, 0.0), 0.0)


if __name__ == "__main__":
    unittest.main()