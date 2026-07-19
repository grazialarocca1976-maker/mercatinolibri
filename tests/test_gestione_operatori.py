import unittest
from unittest.mock import patch, MagicMock

import gestione_operatori as go


class TestGestioneOperatori(unittest.TestCase):
    def test_hash_password_stabile_con_salt(self):
        digest1, salt = go._hash_password("segreta", salt="abc123")
        digest2, _ = go._hash_password("segreta", salt="abc123")
        self.assertEqual(digest1, digest2)
        self.assertEqual(salt, "abc123")
        self.assertEqual(len(digest1), 64)  # SHA-256 hex

    def test_hash_password_salt_diverso_da_hash_diverso(self):
        d1, _ = go._hash_password("segreta", salt="saltA")
        d2, _ = go._hash_password("segreta", salt="saltB")
        self.assertNotEqual(d1, d2)

    def test_verifica_password_corretta(self):
        digest, salt = go._hash_password("segreta")
        self.assertTrue(go.verifica_password("segreta", digest, salt))

    def test_verifica_password_errata(self):
        digest, salt = go._hash_password("segreta")
        self.assertFalse(go.verifica_password("sbagliata", digest, salt))

    @patch("gestione_operatori.requests.post")
    @patch("gestione_operatori.requests.get")
    def test_crea_operatore_successo(self, mock_get, mock_post):
        mock_get.return_value = MagicMock(status_code=200, json=lambda: [])
        mock_post.return_value = MagicMock(status_code=201)
        ok, msg = go.crea_operatore("luigi", "pass1234")
        self.assertTrue(ok)
        self.assertIn("luigi", msg)
        mock_post.assert_called_once()

    @patch("gestione_operatori.requests.post")
    @patch("gestione_operatori.requests.get")
    def test_crea_operatore_duplicato(self, mock_get, mock_post):
        mock_get.return_value = MagicMock(status_code=200, json=lambda: [{"username": "luigi"}])
        ok, msg = go.crea_operatore("luigi", "pass1234")
        self.assertFalse(ok)
        self.assertIn("esiste gia", msg)
        mock_post.assert_not_called()

    @patch("gestione_operatori.requests.post")
    @patch("gestione_operatori.requests.get")
    def test_crea_operatore_password_corta(self, mock_get, mock_post):
        mock_get.return_value = MagicMock(status_code=200, json=lambda: [])
        ok, msg = go.crea_operatore("luigi", "abc")
        self.assertFalse(ok)
        self.assertIn("almeno 4", msg)
        mock_post.assert_not_called()

    @patch("gestione_operatori.requests.delete")
    def test_elimina_operatore_admin_bloccato(self, mock_del):
        ok, msg = go.elimina_operatore("admin")
        self.assertFalse(ok)
        self.assertIn("admin master", msg)
        mock_del.assert_not_called()

    @patch("gestione_operatori.requests.delete")
    def test_elimina_operatore_successo(self, mock_del):
        mock_del.return_value = MagicMock(status_code=204)
        ok, msg = go.elimina_operatore("luigi")
        self.assertTrue(ok)
        mock_del.assert_called_once()

    @patch("gestione_operatori.requests.patch")
    def test_cambia_ruolo_successo(self, mock_patch):
        mock_patch.return_value = MagicMock(status_code=200)
        ok, msg = go.cambia_ruolo("luigi", "admin")
        self.assertTrue(ok)
        mock_patch.assert_called_once()

    @patch("gestione_operatori.requests.patch")
    def test_cambia_ruolo_non_valido(self, mock_patch):
        ok, msg = go.cambia_ruolo("luigi", "superuser")
        self.assertFalse(ok)
        self.assertIn("non valido", msg)
        mock_patch.assert_not_called()

    @patch("gestione_operatori.requests.get")
    def test_lista_operatori(self, mock_get):
        mock_get.return_value = MagicMock(status_code=200, json=lambda: [{"username": "a", "ruolo": "admin"}])
        lista = go.lista_operatori()
        self.assertEqual(len(lista), 1)
        self.assertEqual(lista[0]["username"], "a")

    @patch("gestione_operatori.requests.get")
    def test_autentica_admin_master(self, mock_get):
        # Non deve nemmeno chiamare la rete per l'admin master
        ok = go.autentica("admin", "Marconi2026")
        self.assertTrue(ok)
        mock_get.assert_not_called()

    @patch("gestione_operatori.requests.get")
    def test_autentica_operatore_valido(self, mock_get):
        digest, salt = go._hash_password("pass1234")
        mock_get.return_value = MagicMock(
            status_code=200, json=lambda: [{"password_hash": digest, "salt": salt}]
        )
        self.assertTrue(go.autentica("luigi", "pass1234"))

    @patch("gestione_operatori.requests.get")
    def test_autentica_operatore_password_errata(self, mock_get):
        digest, salt = go._hash_password("pass1234")
        mock_get.return_value = MagicMock(
            status_code=200, json=lambda: [{"password_hash": digest, "salt": salt}]
        )
        self.assertFalse(go.autentica("luigi", "sbagliata"))


if __name__ == "__main__":
    unittest.main()