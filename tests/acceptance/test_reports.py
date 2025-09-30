import asyncio
import pytest
from app.reports.service import ReportService


@pytest.mark.asyncio
async def test_report_builds_without_errors(monkeypatch):
    class DummyTG:
        async def send_message(self, *a, **k):
            return True

    svc = ReportService(db=None, telegram_client=DummyTG())
    txt = await svc._build_report_text("Morning")
    assert "Report" in txt or "rapport" in txt.lower()
