import unittest
from unittest.mock import patch, MagicMock

import logger_supabase as ls


class TestLoggerSupabase(unittest.TestCase):
    @patch("logger_supabase.requests.post")
    def test_log_errore_invia_payload(self, mock_post):
        mock_post.return_value = MagicMock()
        ls.log_errore(tipo="test", messaggio="errore!", operatore="mario", pagina="cassa")
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        payload = kwargs.get("json") or (args[1] if len(args) > 1 else None)
        self.assertEqual(payload["tipo"], "test")
        self.assertEqual(payload["messaggio"], "errore!")
        self.assertEqual(payload["operatore"], "mario")

    @patch("logger_supabase.requests.post")
    def test_log_errore_troncamento(self, mock_post):
        mock_post.return_value = MagicMock()
        ls.log_errore(messaggio="x" * 600, dettaglio="y" * 3000)
        args, kwargs = mock_post.call_args
        payload = kwargs.get("json")
        self.assertLessEqual(len(payload["messaggio"]), 500)
        self.assertLessEqual(len(payload["dettaglio"]), 2000)

    @patch("logger_supabase.requests.post", side_effect=Exception("rete giu"))
    def test_log_errore_non_solleva(self, mock_post):
        # Non deve mai sollevare eccezioni
        try:
            ls.log_errore("test", "msg")
        except Exception:
            self.fail("log_errore ha sollevato un'eccezione")

    @patch("logger_supabase.requests.get")
    def test_leggi_log_errori_successo(self, mock_get):
        mock_get.return_value = MagicMock(status_code=200, json=lambda: [{"id": 1}])
        risultati = ls.leggi_log_errori()
        self.assertEqual(len(risultati), 1)

    @patch("logger_supabase.requests.get")
    def test_leggi_log_errori_errore_restituisce_lista_vuota(self, mock_get):
        mock_get.return_value = MagicMock(status_code=500, json=lambda: [])
        self.assertEqual(ls.leggi_log_errori(), [])

    @patch("logger_supabase.requests.get", side_effect=Exception("rete"))
    def test_leggi_log_errori_eccezione_lista_vuota(self, mock_get):
        self.assertEqual(ls.leggi_log_errori(), [])


if __name__ == "__main__":
    unittest.main()