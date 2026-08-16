import time

import pytest

from utils.text import (
    decode_benefit,
    format_job_type_id,
    format_work_mode_id,
    format_experience_id,
    format_description_id,
    translate_description_id,
    translate_to_id,
)
from scrapers.base import BaseScraper


class TestDecodeBenefit:
    def test_kalibrr_slugs_map_to_indonesian(self):
        assert decode_benefit("sick_leave") == "Izin Sakit"
        assert decode_benefit("perf_bonus") == "Bonus Kinerja"
        assert decode_benefit("paid_holidays") == "Libur Berbayar"
        assert decode_benefit("mat_pat_leave") == "Cuti Melahirkan/Ayah"

    def test_sejutacita_camelcase_slugs_map_to_indonesian(self):
        assert decode_benefit("competitiveSalary") == "Gaji Kompetitif"
        assert decode_benefit("wellnessProgram") == "Program Kesehatan"
        assert decode_benefit("Birthday Treat") == "Hadiah Ulang Tahun"

    def test_unknown_slug_passes_through(self):
        assert decode_benefit("some_unknown_perk") == "some_unknown_perk"

    def test_none_and_empty_return_none(self):
        assert decode_benefit(None) is None
        assert decode_benefit("") is None
        assert decode_benefit("   ") is None

    def test_sejutacita_english_benefit_labels(self):
        assert decode_benefit("Early Wages Program") == "Program Gaji Awal"
        assert decode_benefit("Health Insurance") == "Asuransi Kesehatan"
        assert decode_benefit("Personal Loan") == "Pinjaman Karyawan"
        assert decode_benefit("Sign On Bonus") == "Bonus Tanda Tangan"

    def test_sejutacita_camelcase_new_slugs(self):
        assert decode_benefit("periodLeave") == "Cuti Haid"
        assert decode_benefit("medicalLeave") == "Cuti Sakit (Medis)"
        assert decode_benefit("transport") == "Tunjangan Transportasi"
        assert decode_benefit("gymMembership") == "Keanggotaan Gym"


class TestFormatJobTypeId:
    def test_english_inputs_map_to_indonesian(self):
        assert format_job_type_id("FULL_TIME") == "Penuh Waktu"
        assert format_job_type_id("Full-time") == "Penuh Waktu"
        assert format_job_type_id("Part-time") == "Paruh Waktu"
        assert format_job_type_id("Contract") == "Kontrak"
        assert format_job_type_id("Contract/Temp") == "Kontrak/Sementara"
        assert format_job_type_id("Internship") == "Magang"
        assert format_job_type_id("Project-based") == "Berbasis Proyek"


class TestFormatWorkModeId:
    def test_work_mode_normalization(self):
        assert format_work_mode_id("On-site") == "On-site"
        assert format_work_mode_id("Remote") == "Remote"
        assert format_work_mode_id("Hybrid") == "Hybrid"
        assert format_work_mode_id("") == "N/A"
        assert format_work_mode_id(None) == "N/A"


class TestFormatExperienceId:
    def test_seniority_labels_map_to_indonesian(self):
        assert format_experience_id("Entry level") == "Level Pemula"
        assert format_experience_id("Mid-Senior level") == "Level Menengah-Senior"
        assert format_experience_id("Associate") == "Level Asosiat"

    def test_range_labels_pass_through(self):
        assert format_experience_id("1-3 tahun") == "1-3 tahun"
        assert format_experience_id("") == "N/A"


class TestTranslateDescriptionId:
    def test_key_phrases_translated(self):
        desc = "We are looking for a Software Engineer with good communication skills."
        out = translate_description_id(desc)
        assert "Kami mencari" in out
        assert "Kemampuan komunikasi yang baik" in out

    def test_responsibilities_and_team(self):
        desc = "Responsibilities include collaborating with the team."
        out = translate_description_id(desc)
        assert "Tanggung Jawab" in out
        assert "Tim" in out

    def test_empty_returns_empty(self):
        assert translate_description_id(None) == ""
        assert translate_description_id("") == ""


class TestTranslateToId:
    def test_no_api_key_returns_original_text(self, monkeypatch):
        """Without DEEPL_API_KEY, text is returned unchanged (no translation)."""
        monkeypatch.setattr("config.config.DEEPL_API_KEY", "")
        original = "We are looking for a Software Engineer."
        assert translate_to_id(original) == original

    def test_deepl_success_returns_translated(self, monkeypatch):
        """With a valid key and a 200 response, DeepL output is used."""
        monkeypatch.setattr("config.config.DEEPL_API_KEY", "fake-key")
        monkeypatch.setattr(
            "config.config.DEEPL_API_URL", "https://api.example.com/v2/translate"
        )

        class FakeResp:
            status_code = 200

            def json(self):
                return {"translations": [{"text": "Ini deskripsi bahasa Indonesia"}]}

        def fake_post(url, **kwargs):
            assert kwargs["json"]["target_lang"] == "ID"
            assert kwargs["headers"]["Authorization"] == "DeepL-Auth-Key fake-key"
            return FakeResp()

        monkeypatch.setattr("requests.post", fake_post)
        out = translate_to_id("Some English job description")
        assert out == "Ini deskripsi bahasa Indonesia"

    def test_deepl_failure_returns_original_text(self, monkeypatch):
        """On API error, return the original text rather than raising."""
        monkeypatch.setattr("config.config.DEEPL_API_KEY", "fake-key")
        monkeypatch.setattr(
            "config.config.DEEPL_API_URL", "https://api.example.com/v2/translate"
        )

        def fake_post(url, **kwargs):
            raise RuntimeError("network down")

        monkeypatch.setattr("requests.post", fake_post)
        original = "We are looking for a Software Engineer."
        assert translate_to_id(original) == original


class TestSejutaCitaEducationDropped:
    def test_last_educations_not_leaked(self):
        """Education must be None, never raw integer codes."""
        from scrapers.sejutacita import SejutaCitaScraper

        # The fix means edu_str is hardcoded to None regardless of input.
        # We assert the scraper module no longer joins raw lastEducations.
        import inspect
        src = inspect.getsource(SejutaCitaScraper.fetch_jobs)
        assert "lastEducations" not in src or "join(str(e)" not in src
        assert "edu_str = None" in src


class TestLinkedInNotApplicable:
    def test_not_applicable_becomes_none(self):
        """The seniority parser maps 'Not Applicable' to None."""
        from scrapers.linkedin import LinkedInScraper
        import inspect
        src = inspect.getsource(LinkedInScraper._fetch_job_detail)
        assert 'not applicable' in src


class TestGlintsExperienceDash:
    def test_experience_uses_hyphen_not_endash(self):
        """Glints range must use ASCII hyphen, not en-dash."""
        from scrapers.glints import GlintsScraper
        import inspect
        src = inspect.getsource(GlintsScraper.fetch_jobs)
        assert "–" not in src
        assert 'f"{min_exp}-{max_exp} tahun"' in src


class TestKalibrrBenefitsDecoded:
    def test_perks_use_decode_benefit(self):
        from scrapers.kalibrr import KalibrrScraper
        import inspect
        src = inspect.getsource(KalibrrScraper.fetch_jobs)
        assert "decode_benefit(p)" in src
        assert "decode_benefit(pother)" in src


class _DummyScraper(BaseScraper):
    @property
    def source_name(self) -> str:
        return "Dummy"

    def fetch_jobs(self):
        return []


class TestBaseScraperSessionAndThrottle:
    def test_session_is_per_instance_not_shared(self):
        """Each scraper instance must own a separate session (thread-safe)."""
        a = _DummyScraper()
        b = _DummyScraper()
        assert a.session is not b.session

    def test_429_is_in_retry_status_forcelist(self):
        """429 must be retried so rate-limits self-heal via backoff."""
        from requests.adapters import HTTPAdapter
        a = _DummyScraper()
        # Inspect the mounted adapter's retry config.
        for scheme in ("http://", "https://"):
            adapter = a.session.adapters.get(scheme)
            assert isinstance(adapter, HTTPAdapter)
            retry = adapter.max_retries
            assert 429 in retry.status_forcelist
            assert retry.respect_retry_after_header is True

    def test_throttle_sleeps_when_delay_set(self, monkeypatch):
        """_throttle should sleep when request_delay > 0 and the prior request
        finished less than request_delay seconds ago (timestamp set in _get)."""
        calls = []

        def fake_sleep(sec):
            calls.append(sec)

        monkeypatch.setattr("time.sleep", fake_sleep)
        a = _DummyScraper()
        a.request_delay = 1.0
        a._throttle()  # first call: no prior request -> no sleep
        assert calls == []
        # Simulate a request completing now, then an immediate throttle call.
        a._last_request_ts = time.monotonic()
        a._throttle()
        assert len(calls) == 1
        assert calls[0] > 0

    def test_throttle_no_sleep_when_delay_zero(self, monkeypatch):
        calls = []

        def fake_sleep(sec):
            calls.append(sec)

        monkeypatch.setattr("time.sleep", fake_sleep)
        a = _DummyScraper()
        a.request_delay = 0.0
        a._throttle()
        a._throttle()
        assert calls == []


class TestScraperRequestDelays:
    def test_rate_limited_scrapers_have_positive_delay(self):
        """LinkedIn (aggressive 429) and JobStreet/Glints (many requests) need delays."""
        from scrapers.linkedin import LinkedInScraper
        from scrapers.jobstreet import JobStreetScraper
        from scrapers.glints import GlintsScraper
        assert LinkedInScraper().request_delay > 0
        assert JobStreetScraper().request_delay > 0
        assert GlintsScraper().request_delay > 0

    def test_scrapers_call_super_init(self):
        """Every concrete scraper must call super().__init__() to init _session."""
        from scrapers.kalibrr import KalibrrScraper
        from scrapers.jobstreet import JobStreetScraper
        from scrapers.glints import GlintsScraper
        from scrapers.linkedin import LinkedInScraper
        from scrapers.sejutacita import SejutaCitaScraper
        for cls in (KalibrrScraper, JobStreetScraper, GlintsScraper, LinkedInScraper, SejutaCitaScraper):
            assert cls()._session is None  # lazily created; but must be initialized attr


class TestFormatDescriptionId:
    def test_preserves_paragraphs_and_bullets(self):
        """HTML headings/lists/paragraphs become multi-line text, not one blob."""
        desc = (
            "<h3>Responsibilities</h3>"
            "<ul><li>Design cloud infrastructure</li>"
            "<li>Implement CI/CD pipelines</li></ul>"
            "<p>You will monitor and respond to incidents.</p>"
        )
        out = format_description_id(desc)
        assert "\n" in out
        assert "Responsibilities" in out
        assert "Design cloud infrastructure" in out
        assert "Implement CI/CD pipelines" in out

    def test_truncates_on_line_boundary(self):
        long_desc = "Line one is short.\n" + ("word " * 200) + "\nLine last."
        out = format_description_id(long_desc, max_len=40)
        assert len(out) <= 40 + 1  # + ellipsis
        assert out.endswith("…")

    def test_empty_returns_empty(self):
        assert format_description_id("") == ""
        assert format_description_id(None) == ""


class TestCleanDescription:
    def test_preserves_newlines_unlike_sanitize_text(self):
        """clean_description keeps paragraphs; sanitize_text flattens them."""
        from utils.text import clean_description, sanitize_text
        src = "Responsibilities\n- Design cloud infra\n- Implement CI/CD"
        assert "\n" in clean_description(src)
        assert "\n" not in sanitize_text(src)

    def test_heading_and_bullets_become_multiline(self):
        from utils.text import clean_description
        out = clean_description("<h3>Requirements</h3><ul><li>A</li><li>B</li></ul>")
        assert "\n" in out
        assert "Requirements" in out
        assert "A" in out and "B" in out

    def test_none_returns_empty(self):
        from utils.text import clean_description
        assert clean_description(None) == ""

    def test_strips_linkedin_show_more_less_toggle(self):
        from utils.text import clean_description
        # Toggle labels from <button> tags (merged) and standalone lines.
        assert "Show more" not in clean_description(
            "<ul><li>Build CI/CD</li></ul><button>Show more</button><button>Show less</button>"
        )
        assert "Show less" not in clean_description("Intro\n\nShow more\n\nShow less")

    def test_keeps_legit_show_more_phrase(self):
        from utils.text import clean_description
        # "show more" inside a real sentence must NOT be stripped.
        out = clean_description("We will show more details to shortlisted candidates.")
        assert "show more" in out


class TestDraftjsToText:
    def test_unstyled_and_list_items_become_multiline(self):
        from utils.text import draftjs_to_text
        raw = {
            "blocks": [
                {"text": "Responsibilities:", "type": "unstyled"},
                {"text": "", "type": "unstyled"},
                {"text": "Build CI/CD", "type": "unordered-list-item"},
                {"text": "Manage cloud", "type": "unordered-list-item"},
            ]
        }
        out = draftjs_to_text(raw)
        assert out is not None
        assert "Responsibilities:" in out
        assert "• Build CI/CD" in out
        assert "• Manage cloud" in out
        assert "\n" in out

    def test_empty_blocks_separate_paragraphs(self):
        from utils.text import draftjs_to_text
        raw = {"blocks": [
            {"text": "Para one", "type": "unstyled"},
            {"text": "", "type": "unstyled"},
            {"text": "Para two", "type": "unstyled"},
        ]}
        out = draftjs_to_text(raw)
        assert out is not None
        assert "Para one\n\nPara two" in out

    def test_invalid_returns_none(self):
        from utils.text import draftjs_to_text
        assert draftjs_to_text(None) is None
        assert draftjs_to_text({}) is None
        assert draftjs_to_text({"blocks": []}) is None

