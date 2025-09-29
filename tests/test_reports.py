import asyncio
from app.reports.service import ReportService
from app.telegram_client import client


def test_report_send():
	async def demo():
		await client.start()
		service = ReportService(db=None, telegram_client=client)
		text = service._build_report("Test")
		# send to yourself for demo; adjust if needed
		await client.send_message("me", text)
		await client.disconnect()
	asyncio.run(demo())