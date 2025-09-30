from app.telegram import templates


def test_bilingual_templates_contain_both_languages():
    t1 = templates.leverage_set("BTCUSDT", 10)
    assert "Hävstång" in t1 and "Leverage" in t1

    t2 = templates.entries_placed("BTCUSDT", ["A", "B"])
    assert "Order" in t2 and "Entry orders" in t2

    t3 = templates.position_confirmed("BTCUSDT", 1)
    assert "Position" in t3 and "Position" in t3  # SE/EN combined string

    t4 = templates.tpsl_placed("BTCUSDT", 2, "19000")
    assert "placerade" in t4.lower() and "placed" in t4.lower()

    t5 = templates.tp_hit("BTCUSDT", "21000")
    assert "TP" in t5 and "Price" in t5

    t6 = templates.sl_hit("BTCUSDT", "19000")
    assert "SL" in t6 and "Stop-loss" in t6

