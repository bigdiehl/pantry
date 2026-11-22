import json
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from recipe_core import push as push_mod
from recipe_core.push import PushStore

ALL = {"test_recipe", "butternut_squash_soup", "black_bean_and_pepper_jack_tostadas"}


def selected(app_module):
    return {r.slug for r in app_module.get_all_recipes() if r.selected}


def test_legacy_email_config_keeps_emailing(app_module):
    app_module._save_schedule_config({"enabled": True, "num_recipes": 2, "day_of_week": 6,
                                      "send_time": "09:00", "recipients": "a@example.com"})
    cfg = app_module._get_schedule_config()
    assert cfg["send_email"] is True
    assert cfg["notify"] is True and cfg["fresh_start"] is True and cfg["frequency_weeks"] == 1


def test_plan_fresh_start_replaces_selection(app_module, monkeypatch):
    sent = []
    monkeypatch.setattr(app_module.PUSH, "send_all", lambda **kw: sent.append(kw) or 1)
    app_module._update_state("test_recipe", selected=True)
    app_module._save_schedule_config({**app_module.PLAN_DEFAULTS, "enabled": True, "num_recipes": 2})

    result = app_module.run_weekly_plan()

    assert len(result["slugs"]) == 2
    assert selected(app_module) == set(result["slugs"])
    assert result["notified"] == 1
    assert sent[0]["url"] == "/" and all(n in sent[0]["body"] for n in result["names"])
    state = app_module._load_state()
    assert state["_week_plan"]["slugs"] == result["slugs"]
    assert all(state[s]["last_used_date"] for s in result["slugs"])


def test_plan_keep_mode_tops_up(app_module, monkeypatch):
    monkeypatch.setattr(app_module.PUSH, "send_all", lambda **kw: 0)
    app_module._update_state("test_recipe", selected=True)
    app_module._save_schedule_config({**app_module.PLAN_DEFAULTS, "enabled": True,
                                      "num_recipes": 2, "fresh_start": False})
    result = app_module.run_weekly_plan()
    assert "test_recipe" in result["slugs"] and len(selected(app_module)) == 2


def test_plan_disabled_and_biweekly_skip(app_module, monkeypatch):
    monkeypatch.setattr(app_module.PUSH, "send_all", lambda **kw: 0)
    assert app_module.run_weekly_plan() == {"skipped": "disabled"}

    app_module._save_schedule_config({**app_module.PLAN_DEFAULTS, "enabled": True, "frequency_weeks": 2})
    state = app_module._load_state()
    state["_week_plan"] = {"created": (datetime.now() - timedelta(days=7)).isoformat(), "slugs": []}
    app_module._save_state(state)
    assert app_module.run_weekly_plan() == {"skipped": "not due"}
    assert "slugs" in app_module.run_weekly_plan(force=True)


def test_schedule_routes_round_trip(client):
    resp = client.post("/schedule/config", json={"enabled": True, "num_recipes": 99, "frequency_weeks": 2,
                                                 "day_of_week": 3, "send_time": "7:5", "notify": True})
    cfg = resp.get_json()["config"]
    assert cfg["num_recipes"] == 14 and cfg["frequency_weeks"] == 2 and cfg["send_time"] == "07:05"
    data = client.get("/schedule/config").get_json()
    assert data["config"]["day_of_week"] == 3 and data["next_run"]
    assert client.get("/plan").status_code == 200


def test_push_store_keys_and_subscriptions(tmp_path):
    store = PushStore(str(tmp_path))
    key = store.public_key
    assert len(key) > 80 and "=" not in key
    assert PushStore(str(tmp_path)).public_key == key          # persisted, not regenerated

    sub = {"endpoint": "https://push.example/abc", "keys": {"p256dh": "x", "auth": "y"}}
    store.add(sub, label="Chrome on Android")
    store.add(sub, label="again")                               # de-duplicated by endpoint
    assert len(store.subscriptions()) == 1 and store.has(sub["endpoint"])
    with pytest.raises(ValueError):
        store.add({"endpoint": ""})
    store.remove(sub["endpoint"])
    assert store.subscriptions() == []


def test_push_send_drops_expired(tmp_path, monkeypatch):
    store = PushStore(str(tmp_path))
    store.add({"endpoint": "https://push.example/ok", "keys": {"p256dh": "x", "auth": "y"}})
    store.add({"endpoint": "https://push.example/gone", "keys": {"p256dh": "x", "auth": "y"}})
    payloads = []

    def fake_webpush(subscription_info, data, **kw):
        if subscription_info["endpoint"].endswith("gone"):
            raise push_mod.WebPushException("gone", response=SimpleNamespace(status_code=410))
        payloads.append(json.loads(data))

    monkeypatch.setattr(push_mod, "webpush", fake_webpush)
    assert store.send_all("Title", "Body", url="/x") == 1
    assert payloads[0] == {"title": "Title", "body": "Body", "url": "/x", "tag": "pantry"}
    assert [s["endpoint"] for s in store.subscriptions()] == ["https://push.example/ok"]


def test_push_routes(client):
    assert client.get("/push/key").get_json()["public_key"]
    sub = {"endpoint": "https://push.example/r", "keys": {"p256dh": "x", "auth": "y"}}
    assert client.post("/push/subscribe", json={"subscription": sub}).get_json()["devices"] == 1
    assert client.post("/push/status", json={"endpoint": sub["endpoint"]}).get_json()["subscribed"]
    assert client.post("/push/unsubscribe", json={"endpoint": sub["endpoint"]}).get_json()["devices"] == 0
