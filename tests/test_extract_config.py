"""Tests for extract_config: api_version loading from env var and YAML."""

import os
import sys
import textwrap
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from extract_config import Config, load_config


# ---------------------------------------------------------------------------
# Default
# ---------------------------------------------------------------------------

def test_default_api_version():
    cfg = load_config()
    assert cfg.api_version == 10


# ---------------------------------------------------------------------------
# YAML loading
# ---------------------------------------------------------------------------

def _write_yaml(content: str) -> str:
    f = tempfile.NamedTemporaryFile('w', suffix='.yml', delete=False, encoding='utf-8')
    f.write(textwrap.dedent(content))
    f.close()
    return f.name


def test_yaml_api_version(tmp_path):
    p = tmp_path / 'cfg.yml'
    p.write_text('paperless:\n  api_version: 9\n', encoding='utf-8')
    cfg = load_config(str(p))
    assert cfg.api_version == 9


def test_yaml_api_version_integer_string(tmp_path):
    p = tmp_path / 'cfg.yml'
    p.write_text('paperless:\n  api_version: "10"\n', encoding='utf-8')
    cfg = load_config(str(p))
    assert cfg.api_version == 10


def test_yaml_invalid_api_version_raises(tmp_path):
    p = tmp_path / 'cfg.yml'
    p.write_text('paperless:\n  api_version: foobar\n', encoding='utf-8')
    with pytest.raises(ValueError, match='api_version'):
        load_config(str(p))


def test_yaml_without_paperless_section_uses_default(tmp_path):
    p = tmp_path / 'cfg.yml'
    p.write_text('fields:\n  invoice_number: Nummer\n', encoding='utf-8')
    cfg = load_config(str(p))
    assert cfg.api_version == 10
    assert cfg.field_invoice_number == 'Nummer'


# ---------------------------------------------------------------------------
# PAPERLESS_API_VERSION env var
# ---------------------------------------------------------------------------

def test_env_var_overrides_default(monkeypatch):
    monkeypatch.setenv('PAPERLESS_API_VERSION', '9')
    cfg = load_config()
    assert cfg.api_version == 9


def test_env_var_overrides_yaml(monkeypatch, tmp_path):
    p = tmp_path / 'cfg.yml'
    p.write_text('paperless:\n  api_version: 9\n', encoding='utf-8')
    monkeypatch.setenv('PAPERLESS_API_VERSION', '10')
    cfg = load_config(str(p))
    assert cfg.api_version == 10


def test_env_var_invalid_raises(monkeypatch):
    monkeypatch.setenv('PAPERLESS_API_VERSION', 'not-a-number')
    with pytest.raises(ValueError, match='PAPERLESS_API_VERSION'):
        load_config()


def test_env_var_absent_uses_yaml(monkeypatch, tmp_path):
    monkeypatch.delenv('PAPERLESS_API_VERSION', raising=False)
    p = tmp_path / 'cfg.yml'
    p.write_text('paperless:\n  api_version: 9\n', encoding='utf-8')
    cfg = load_config(str(p))
    assert cfg.api_version == 9
