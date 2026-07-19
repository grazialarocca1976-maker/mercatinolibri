import unittest

from gestore_etichette import genera_preview_etichette, genera_griglia_a4_bytes


class TestGestoreEtichettePdf(unittest.TestCase):
    def test_genera_preview_etichette(self):
        payload = [
            {"id_libro": 12, "titolo": "Il titolo A"},
            {"id": 15, "titolo": "Il titolo B"},
        ]
        righe = genera_preview_etichette(payload)
        self.assertEqual(len(righe), 2)
        self.assertIn("12", righe[0])
        self.assertIn("Il titolo A", righe[0])
        self.assertIn("15", righe[1])

    def test_genera_preview_etichette_vuoto(self):
        self.assertEqual(genera_preview_etichette([]), [])
        self.assertEqual(genera_preview_etichette(None), [])

    def test_genera_griglia_a4_bytes(self):
        payload = [
            {"id_libro": 12, "titolo": "Il titolo A", "codice_personale": "ROS12AB", "id_venditore": 3},
            {"id": 15, "titolo": "Il titolo B", "codice_personale": "VER99XY", "id_venditore": 7},
        ]
        pdf = genera_griglia_a4_bytes(payload)
        self.assertIsNotNone(pdf)
        self.assertTrue(pdf.startswith(b"%PDF"))

    def test_genera_griglia_a4_bytes_vuoto(self):
        self.assertIsNone(genera_griglia_a4_bytes([]))

    def test_genera_griglia_a4_bytes_layout_a5(self):
        payload = [{"id_libro": 1, "titolo": "Libro"}]
        pdf = genera_griglia_a4_bytes(payload, layout="a5")
        self.assertIsNotNone(pdf)
        self.assertTrue(pdf.startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()