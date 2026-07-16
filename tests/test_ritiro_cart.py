import unittest

from ritiro import aggiorna_carrello_ritiro


class TestRitiroCart(unittest.TestCase):
    def test_aggiorna_carrello_ritiro_unisce_doppioni(self):
        carrello = [{"isbn": "978123", "titolo": "Titolo test", "prezzo": 10.0, "quantita": 1}]

        aggiorna_carrello_ritiro(carrello, {"isbn": "978123", "titolo": "Titolo test", "prezzo": 10.0}, 2)

        self.assertEqual(len(carrello), 1)
        self.assertEqual(carrello[0]["quantita"], 3)


if __name__ == "__main__":
    unittest.main()
