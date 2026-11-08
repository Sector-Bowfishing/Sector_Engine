"""conditions_tiles_flag: preset validation with TileFlags semantics, the single-parameter edit, read-back, the serve refusal. Offline."""
import copy
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import conditions_tiles_flag as F  # noqa: E402

OWNER_STRING = ('{"version":1,"tiles":{"humidity":{"mode":"shadow"},"pressure":{"mode":"shadow"},"temperature":{"mode":"shadow"},'
                '"sky":{"mode":"shadow"},"wind":{"mode":"shadow"}}}')

TEMPLATE = {
    "conditions": [{"name": "ios", "expression": "device.os == 'ios'"}],
    "parameters": {
        "conditions_config": {"defaultValue": {"value": "{\"a\":1}"}, "valueType": "JSON"},
        "feature_x": {"defaultValue": {"value": "true"}, "conditionalValues": {"ios": {"value": "false"}}, "valueType": "BOOLEAN"},
    },
    "parameterGroups": {"g": {"parameters": {"in_group": {"defaultValue": {"value": "1"}}}}},
    "version": {"versionNumber": "41", "updateTime": "2026-11-01T00:00:00Z"},
}


def test_weather_shadow_is_exactly_the_owner_string():
    assert F.WEATHER_SHADOW == OWNER_STRING


def test_presets_validate_and_match_tileflags_semantics():
    for preset, value in F.PRESETS.items():
        assert F.validate_preset(preset, value) == []
    modes = F.effective_modes(F.WEATHER_SHADOW)
    assert {k for k, m in modes.items() if m == "shadow"} == {"humidity", "pressure", "temperature", "sky", "wind"}
    assert all(m == "off" for k, m in modes.items() if k not in F.WEATHER_TILES)
    assert set(F.effective_modes(None).values()) == {"off"}


def test_tile_keys_mirror_swift_enum():
    swift = open(os.path.join(os.path.dirname(__file__), "..", "..", "..", "Sources/SectorEngine/Conditions/TileFlags.swift")).read()
    line = next(l for l in swift.splitlines() if l.strip().startswith("case humidity"))
    keys = tuple(k.strip() for k in line.strip()[len("case "):].split(","))
    assert keys == F.TILE_KEYS
    for mode in F.TILE_MODES:
        assert f"case {mode}\n" in swift


@pytest.mark.parametrize("raw, want", [
    (None, {}), ("", {}), ("not json", {}), ("[]", {}), ('{"tiles": 3}', {}),
    ('{"version":1,"tiles":{"bogus":{"mode":"serve"},"wind":{"mode":"shadow"}}}', {"wind": "shadow"}),   # unknown key ignored
    ('{"version":1,"tiles":{"wind":{"mode":"loud"}}}', {}),                                             # unknown mode -> off
    ('{"version":1,"tiles":{"wind":{"mode":"shadow","lakes":"x"}}}', {}),                               # malformed lakes -> off
    ('{"version":1,"tiles":{"wind":{"mode":"shadow","lakes":["A|AL"]}}}', {"wind": "shadow"}),
])
def test_parse_mirrors_tileflags_fail_safe(raw, want):
    got = {k: v["mode"] for k, v in F.parse_tile_flags(raw)["tiles"].items()}
    assert got == want


@pytest.mark.parametrize("raw", [
    OWNER_STRING.replace('"wind":{"mode":"shadow"}', '"wind":{"mode":"serve"}'),
    OWNER_STRING.replace('"sky":{"mode":"shadow"}', '"sky":{"mode":"shadow"},"clarity":{"mode":"serve"}'),
])
def test_anything_with_serve_is_refused(raw):
    errs = F.validate_preset("weather-shadow", raw)
    assert any("serve" in e for e in errs)


@pytest.mark.parametrize("raw", [
    OWNER_STRING.replace('"version":1', '"version":2'),
    OWNER_STRING.replace('"sky":{"mode":"shadow"}', '"sky":{"mode":"shadow"},"bogus":{"mode":"shadow"}'),
    OWNER_STRING.replace('"sky":{"mode":"shadow"}', '"sky":{"mode":"shadow","lakes":["Guntersville|AL"]}'),
    OWNER_STRING.replace(',"wind":{"mode":"shadow"}', ''),
    OWNER_STRING.replace('"sky":{"mode":"shadow"}', '"sky":{"mode":"shadow"},"clarity":{"mode":"shadow"}'),
])
def test_stricter_than_the_parser(raw):
    assert F.validate_preset("weather-shadow", raw)


def test_unknown_or_serve_preset_refused_by_cli(capsys):
    assert F.main(["plan", "--preset", "serve"]) == 1
    assert F.main(["plan", "--preset", "weather-serve"]) == 1
    assert F.main(["plan", "--preset", "weather-shadow"]) == 0


def test_apply_changes_only_the_parameter_and_drops_version():
    before = copy.deepcopy(TEMPLATE)
    new = F.apply_preset(before, "weather-shadow")
    assert before == TEMPLATE                                   # input untouched
    assert "version" not in new
    assert new["parameters"][F.PARAM] == {"defaultValue": {"value": OWNER_STRING}, "valueType": "JSON"}
    assert F.without_param(new) == F.without_param(TEMPLATE)
    off = F.apply_preset({**new, "version": {"versionNumber": "42"}}, "off")
    assert F.PARAM not in off["parameters"] and F.without_param(off) == F.without_param(TEMPLATE)


def test_apply_keeps_an_existing_description():
    t = copy.deepcopy(TEMPLATE)
    t["parameters"][F.PARAM] = {"defaultValue": {"value": "{}"}, "description": "per-tile flags", "valueType": "JSON"}
    assert F.apply_preset(t, "weather-shadow")["parameters"][F.PARAM]["description"] == "per-tile flags"


def test_preflight_refusals():
    assert F.preflight(TEMPLATE, "weather-shadow") == []
    g = copy.deepcopy(TEMPLATE)
    g["parameterGroups"]["g"]["parameters"][F.PARAM] = {"defaultValue": {"value": "{}"}}
    assert any("group" in e for e in F.preflight(g, "weather-shadow"))
    c = copy.deepcopy(TEMPLATE)
    c["parameters"][F.PARAM] = {"defaultValue": {"value": "{}"}, "conditionalValues": {"ios": {"value": "{}"}}}
    assert any("conditional" in e for e in F.preflight(c, "off"))
    s = copy.deepcopy(TEMPLATE)
    s["parameters"][F.PARAM] = {"defaultValue": {"value": OWNER_STRING.replace('"shadow"}}}', '"serve"}}}')}}
    assert any("CURRENT" in e for e in F.preflight(s, "weather-shadow"))
    assert F.preflight(s, "off") == []                          # off (the rollback) is always allowed


def test_readback_detects_collateral_change_and_wrong_value():
    after = F.apply_preset(TEMPLATE, "weather-shadow")
    after["version"] = {"versionNumber": "42"}
    assert F.verify_readback(TEMPLATE, after, "weather-shadow") == []
    bad = copy.deepcopy(after)
    bad["parameters"]["conditions_config"]["defaultValue"]["value"] = "{}"
    assert F.verify_readback(TEMPLATE, bad, "weather-shadow")
    wrong = copy.deepcopy(after)
    wrong["parameters"][F.PARAM]["defaultValue"]["value"] = OWNER_STRING.replace('"sky":{"mode":"shadow"},', "")
    assert F.verify_readback(TEMPLATE, wrong, "weather-shadow")
    reformatted = copy.deepcopy(after)
    reformatted["parameters"][F.PARAM]["defaultValue"]["value"] = json.dumps(json.loads(OWNER_STRING), indent=2)
    assert F.verify_readback(TEMPLATE, reformatted, "weather-shadow") == []
    off = F.apply_preset(after, "off")
    off["version"] = {"versionNumber": "43"}
    assert F.verify_readback(after, off, "off") == []


class FakeRC:
    """The REST surface apply uses: GET (with ETag), PUT with If-Match, validate_only."""

    def __init__(self, template):
        self.template, self.etag, self.puts = copy.deepcopy(template), "etag-1", []

    def __call__(self, method, url, token, body=None, etag=None):
        if method == "GET":
            return 200, copy.deepcopy(self.template), self.etag
        assert etag == self.etag, "If-Match must carry the ETag of the read"
        self.puts.append(url)
        if "validate_only=true" in url:
            return 200, body, self.etag
        n = int(self.template["version"]["versionNumber"]) + 1
        self.template = {**copy.deepcopy(body), "version": {"versionNumber": str(n)}}
        self.etag = f"etag-{n}"
        return 200, self.template, self.etag


def test_apply_end_to_end_with_fake(monkeypatch, capsys):
    fake = FakeRC(TEMPLATE)
    monkeypatch.setattr(F, "_request", fake)
    monkeypatch.setenv("RC_ACCESS_TOKEN", "t")
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    assert F.main(["apply", "--preset", "weather-shadow", "--project", "p"]) == 0
    assert [("validate_only" in u) for u in fake.puts] == [True, False]
    assert F.current_value(fake.template) == OWNER_STRING
    out = capsys.readouterr().out
    assert "BEFORE: 41" in out and "AFTER:  42" in out
    assert F.main(["apply", "--preset", "weather-shadow", "--project", "p"]) == 0     # idempotent: no second write
    assert len(fake.puts) == 2
    assert F.main(["apply", "--preset", "off", "--project", "p"]) == 0
    assert F.PARAM not in fake.template["parameters"]


def test_apply_dry_run_writes_nothing(monkeypatch):
    fake = FakeRC(TEMPLATE)
    monkeypatch.setattr(F, "_request", fake)
    monkeypatch.setenv("RC_ACCESS_TOKEN", "t")
    assert F.main(["apply", "--preset", "weather-shadow", "--project", "p", "--dry-run"]) == 0
    assert all("validate_only" in u for u in fake.puts) and F.PARAM not in fake.template["parameters"]


def test_restore_template_only_when_nothing_else_changed():
    after = F.apply_preset(TEMPLATE, "weather-shadow")
    after["version"] = {"versionNumber": "42"}
    r = F.restore_template(TEMPLATE, after)
    assert F.PARAM not in r["parameters"] and F.without_param(r) == F.without_param(TEMPLATE)
    other = copy.deepcopy(after)
    other["parameters"]["conditions_config"]["defaultValue"]["value"] = "{}"
    assert F.restore_template(TEMPLATE, other) is None


def test_failed_readback_restores_the_previous_value(monkeypatch, capsys):
    fake = FakeRC(TEMPLATE)

    def mangling(method, url, token, body=None, etag=None):     # the server stores a different value than was sent
        r = fake(method, url, token, body, etag)
        if method == "PUT" and "validate_only" not in url and F.PARAM in (body.get("parameters") or {}):
            fake.template["parameters"][F.PARAM]["defaultValue"]["value"] = "{}"
        return r
    monkeypatch.setattr(F, "_request", mangling)
    monkeypatch.setenv("RC_ACCESS_TOKEN", "t")
    assert F.main(["apply", "--preset", "weather-shadow", "--project", "p"]) == 1
    assert F.PARAM not in fake.template["parameters"] and "RESTORED" in capsys.readouterr().out


def test_http_error_prints_no_body(monkeypatch):
    import io
    import urllib.error

    def boom(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 403, "x", {}, io.BytesIO(b'{"error":{"status":"PERMISSION_DENIED","message":"project 123456789012"}}'))
    monkeypatch.setattr(F.urllib.request, "urlopen", boom)
    with pytest.raises(RuntimeError) as e:
        F._request("GET", "https://x", "t")
    assert "PERMISSION_DENIED" in str(e.value) and "123456789012" not in str(e.value)
