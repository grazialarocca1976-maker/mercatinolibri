import json
import unittest
from unittest.mock import patch

import export_fine_anno as ef


class TestExportFineAnno(unittest.TestCase):
    def _dati_finti(self):
        clienti = [
            {"id": 1, "codice_personale": "ROS12AB0001", "nome": "Mario", "cognome": "Rossi"},
        ]
        catalogo = [
            {"isbn": "9788801", "titolo": "Matematica", "prezzo_copertina": 20.0},
        ]
        copie = [
            {
                "id_libro": 10,
                "isbn": "9788801",
                "id_venditore": 1,
                "stato": "venduto",
                "prezzo_inserito_mano": 0.0,  # usa prezzo copertina
                "metodo_pagamento": "Contanti",
                "data_vendita": "2026-07-19",
            },
            {
                "id_libro": 11,
                "isbn": "9788801",
                "id_venditore": 1,
                "stato": "disponibile",
                "prezzo_inserito_mano": 20.0,
            },
        ]
        return clienti, catalogo, copie

    @patch("export_fine_anno._get")
    def test_genera_resoconto_struttura(self, mock_get):
        clienti, catalogo, copie = self._dati_finti()
        mock_get.side_effect = [clienti, copie, catalogo]

        testo_json, nome_file = ef.genera_resoconto_fine_anno()
        resoconto = json.loads(testo_json)

        self.assertIn("riepilogo_cassa", resoconto)
        self.assertIn("liquidazioni_per_cliente", resoconto)
        self.assertEqual(resoconto["riepilogo_cassa"]["n_libri_venduti"], 1)
        self.assertEqual(resoconto["riepilogo_cassa"]["n_clienti_totali"], 1)
        # 1 libro venduto a 20€ copertina -> vendita = 20/2 + 0.50 = 10.50 contanti
        self.assertAlmostEqual(resoconto["riepilogo_cassa"]["totale_contanti"], 10.50, places=2)
        self.assertAlmostEqual(resoconto["riepilogo_cassa"]["totale_bancomat"], 0.0, places=2)

    @patch("export_fine_anno._get")
    def test_genera_resoconto_liquidazione(self, mock_get):
        clienti, catalogo, copie = self._dati_finti()
        mock_get.side_effect = [clienti, copie, catalogo]

        testo_json, _ = ef.genera_resoconto_fine_anno()
        resoconto = json.loads(testo_json)
        liq = resoconto["liquidazioni_per_cliente"]
        self.assertEqual(len(liq), 1)
        self.assertEqual(liq[0]["id_cliente"], 1)
        # 1 libro venduto: liquidazione = 20/2 - 0.50 = 9.50; rimborso spese = 0.50
        self.assertAlmostEqual(liq[0]["totale_da_liquidare"], 9.50, places=2)
        self.assertAlmostEqual(liq[0]["rimborso_spese"], 0.50, places=2)
        self.assertAlmostEqual(liq[0]["totale_da_dare_cliente"], 10.00, places=2)
        # 1 libro da restituire
        self.assertEqual(len(liq[0]["libri_da_restituire"]), 1)

    @patch("export_fine_anno._get")
    def test_genera_resoconto_nome_file(self, mock_get):
        clienti, catalogo, copie = self._dati_finti()
        mock_get.side_effect = [clienti, copie, catalogo]
        _, nome_file = ef.genera_resoconto_fine_anno()
        self.assertTrue(nome_file.startswith("resoconto_fine_anno_"))
        self.assertTrue(nome_file.endswith(".json"))


if __name__ == "__main__":
    unittest.main()