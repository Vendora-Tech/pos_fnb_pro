"""Test aturan perhitungan status lisensi (T010).

Menguji fungsi murni ``compute_state`` dari
``addons/pos_saas_license/models/license_verifier.py`` sesuai tabel
"Aturan Perhitungan Status" di ``specs/001-pos-saas-license/data-model.md``.

Seluruh tanggal dilewatkan eksplisit; tidak ada pemanggilan tanggal nyata,
sehingga hasilnya deterministik. Konvensi penamaan kasus mengikuti contoh di
``data-model.md``: H±N berarti tanggal jatuh tempo (``until``) berada N hari
dari ``today``, sehingga ``days_left = until - today = N``.
"""

from datetime import date, timedelta

from odoo.addons.pos_saas_license.models.license_verifier import (
    compute_state,
    decode_and_verify,
)
from odoo.tests.common import TransactionCase

from .common import LicenseTestMixin


class TestLicenseState(LicenseTestMixin, TransactionCase):
    """Batas status ``compute_state`` dengan ``grace=7`` dan ``warning_days=14``."""

    # Tanggal acuan test; semua kasus dihitung relatif ke sini.
    BASE_TODAY = date(2026, 6, 1)
    DEFAULT_DB_UUID = "test-db-uuid"

    # -- Helper ------------------------------------------------------------

    def _payload(self, **overrides):
        """Buat payload valid lewat token yang ditandatangani mixin."""
        return decode_and_verify(self.make_token(**overrides))

    def _payload_days_left(self, days_left, **overrides):
        """Payload subscription dengan ``until = BASE_TODAY + days_left`` hari."""
        until = self.BASE_TODAY + timedelta(days=days_left)
        return self._payload(until=until.isoformat(), **overrides)

    def _state(self, payload, today=None, db_uuid=None, **kwargs):
        """Panggil ``compute_state`` dengan ``today`` dan ``db_uuid`` eksplisit."""
        return compute_state(
            payload,
            self.BASE_TODAY if today is None else today,
            self.DEFAULT_DB_UUID if db_uuid is None else db_uuid,
            **kwargs,
        )

    # -- Batas tanggal subscription (grace=7) ------------------------------

    def test_active_at_h_minus_15(self):
        """H-15: masih 15 hari lagi, di luar ambang peringatan 14 hari."""
        state, days_left, _reason = self._state(self._payload_days_left(15))
        self.assertEqual("active", state)
        self.assertEqual(15, days_left)

    def test_warning_at_h_minus_14(self):
        """H-14: tepat di ambang ``warning_days``, masuk peringatan."""
        state, days_left, _reason = self._state(self._payload_days_left(14))
        self.assertEqual("warning", state)
        self.assertEqual(14, days_left)

    def test_warning_on_expiry_day(self):
        """H0: ``until`` sama dengan hari ini, masih warning (belum lewat)."""
        state, days_left, _reason = self._state(self._payload_days_left(0))
        self.assertEqual("warning", state)
        self.assertEqual(0, days_left)

    def test_grace_on_first_day_after_expiry(self):
        """H+1: satu hari setelah jatuh tempo, masuk grace period."""
        state, days_left, _reason = self._state(self._payload_days_left(-1))
        self.assertEqual("grace", state)
        self.assertEqual(-1, days_left)

    def test_grace_on_last_grace_day(self):
        """H+7: hari terakhir grace untuk ``grace=7``, masih grace."""
        state, days_left, _reason = self._state(self._payload_days_left(-7))
        self.assertEqual("grace", state)
        self.assertEqual(-7, days_left)

    def test_expired_after_grace_period(self):
        """H+8: melewati ``grace=7``, status expired."""
        state, days_left, _reason = self._state(self._payload_days_left(-8))
        self.assertEqual("expired", state)
        self.assertEqual(-8, days_left)

    def test_grace_zero_expired_on_first_day_after_expiry(self):
        """``grace=0``: H+1 langsung expired tanpa grace period."""
        payload = self._payload_days_left(-1, grace=0)
        state, days_left, _reason = self._state(payload)
        self.assertEqual("expired", state)
        self.assertEqual(-1, days_left)

    def test_custom_warning_days_widens_warning_band(self):
        """``warning_days`` yang lebih besar memperlebar pita peringatan."""
        payload = self._payload_days_left(20)
        state, days_left, _reason = self._state(payload, warning_days=30)
        self.assertEqual("warning", state)
        self.assertEqual(20, days_left)

    # -- Perpetual ---------------------------------------------------------

    def test_perpetual_is_always_active(self):
        """Token perpetual tanpa ``until`` tidak pernah kedaluwarsa."""
        payload = self._payload(typ="perpetual", until=None)
        state, _days_left, _reason = self._state(payload)
        self.assertEqual("active", state)

    def test_perpetual_is_active_in_year_2099(self):
        """Perpetual tetap active meski ``today`` jauh di masa depan."""
        payload = self._payload(typ="perpetual", until=None)
        state, _days_left, _reason = self._state(payload, today=date(2099, 1, 1))
        self.assertEqual("active", state)

    # -- Penolakan (invalid) -----------------------------------------------

    def test_not_yet_effective_is_invalid(self):
        """``from`` di masa depan membuat lisensi belum berlaku (invalid)."""
        today = date(2026, 5, 1)
        start = (today + timedelta(days=1)).isoformat()
        until = (today + timedelta(days=200)).isoformat()
        payload = self._payload(**{"from": start, "until": until})
        state, _days_left, _reason = self._state(payload, today=today)
        self.assertEqual("invalid", state)

    def test_matching_database_uuid_is_active(self):
        """``db_uuid`` payload yang cocok tetap dihitung normal."""
        payload = self._payload_days_left(30)
        state, days_left, _reason = self._state(payload)
        self.assertEqual("active", state)
        self.assertEqual(30, days_left)

    def test_mismatched_database_uuid_is_invalid(self):
        """``db_uuid`` tidak cocok dengan database tenant membuat invalid."""
        payload = self._payload_days_left(30)
        state, _days_left, _reason = self._state(payload, db_uuid="other-db-uuid")
        self.assertEqual("invalid", state)
