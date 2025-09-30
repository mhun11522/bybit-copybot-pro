from decimal import Decimal
from app.telegram import templates


def test_templates_include_source_channel_name():
    src = "MySignalChannel"
    t1 = templates.leverage_set("BTCUSDT", 10, source=src)
    t2 = templates.entries_placed("BTCUSDT", ["L1"], source=src)
    t3 = templates.position_confirmed("BTCUSDT", Decimal("0.01"), Decimal("20000"), source=src)
    t4 = templates.tpsl_placed("BTCUSDT", 2, "19000", source=src)
    t5 = templates.tp_hit("BTCUSDT", "21000", source=src)
    t6 = templates.sl_hit("BTCUSDT", "19000", source=src)

    for txt in (t1, t2, t3, t4, t5, t6):
        assert "Källa/Source:" in txt and src in txt

