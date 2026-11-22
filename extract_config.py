"""Configuration: Paperless field/tag names and their defaults."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
import os


@dataclass
class Config:
    # Paperless REST API version (overridable via PAPERLESS_API_VERSION or config.yml)
    api_version: int = 10

    # Paperless custom field display names
    field_invoice_number:   str = 'Rechnungsnummer'
    field_invoice_date:     str = 'Rechnungsdatum'
    field_due_date:         str = 'Fällig am'
    field_amount:           str = 'Rechnungssumme'
    field_payee:            str = 'Zahlungsempfänger'
    field_iban:             str = 'IBAN'
    field_bic:              str = 'BIC'
    field_payment_reference: str = 'Zahlungsreferenz'
    field_data_source:      str = 'Rechnungs-Datenquelle'

    # Paperless tag names
    tag_inbox:        str = 'unbearbeitet'
    tag_erechnung:    str = 'Auslesen: E-Rechnung'
    tag_girocode:     str = 'Auslesen: GiroCode'
    tag_not_found:    str = 'Auslesen: nichts gefunden'
    tag_conflict:     str = 'Auslesen: Widerspruch'
    tag_credit_note:  str = 'Gutschrift'

    def all_fields(self) -> list[dict]:
        """Return REQUIRED_FIELDS list for setup_paperless, using configured names."""
        return [
            {'name': self.field_invoice_number,    'data_type': 'string'},
            {'name': self.field_invoice_date,       'data_type': 'date'},
            {'name': self.field_due_date,           'data_type': 'date'},
            {'name': self.field_amount,             'data_type': 'monetary'},
            {'name': self.field_payee,              'data_type': 'string'},
            {'name': self.field_iban,               'data_type': 'string'},
            {'name': self.field_bic,                'data_type': 'string'},
            {'name': self.field_payment_reference,  'data_type': 'string'},
            {
                'name': self.field_data_source,
                'data_type': 'select',
                'extra_data': {'select_options': ['E-Rechnung', 'GiroCode', 'manuell']},
            },
        ]

    def all_tags(self) -> list[str]:
        return [
            self.tag_erechnung,
            self.tag_girocode,
            self.tag_not_found,
            self.tag_conflict,
            self.tag_credit_note,
        ]


_FIELD_KEYS = {
    'invoice_number':    'field_invoice_number',
    'invoice_date':      'field_invoice_date',
    'due_date':          'field_due_date',
    'amount':            'field_amount',
    'payee':             'field_payee',
    'iban':              'field_iban',
    'bic':               'field_bic',
    'payment_reference': 'field_payment_reference',
    'data_source':       'field_data_source',
}

_TAG_KEYS = {
    'inbox':       'tag_inbox',
    'erechnung':   'tag_erechnung',
    'girocode':    'tag_girocode',
    'not_found':   'tag_not_found',
    'conflict':    'tag_conflict',
    'credit_note': 'tag_credit_note',
}


def load_config(path: Optional[str] = None) -> Config:
    """Load config from a YAML file. Falls back to defaults for missing keys.

    PAPERLESS_API_VERSION env var always overrides file and default.
    """
    cfg = Config()

    if path is not None:
        try:
            import yaml
        except ImportError:
            raise ImportError('PyYAML required for config file: pip install pyyaml')

        with open(path, encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}

        for yaml_key, attr in _FIELD_KEYS.items():
            value = data.get('fields', {}).get(yaml_key)
            if value is not None:
                setattr(cfg, attr, str(value))

        for yaml_key, attr in _TAG_KEYS.items():
            value = data.get('tags', {}).get(yaml_key)
            if value is not None:
                setattr(cfg, attr, str(value))

        raw_ver = data.get('paperless', {}).get('api_version')
        if raw_ver is not None:
            try:
                cfg.api_version = int(raw_ver)
            except (ValueError, TypeError):
                raise ValueError(
                    f'config.yml: paperless.api_version muss eine ganze Zahl sein, '
                    f'erhalten: {raw_ver!r}'
                )

    # Env var takes the highest precedence
    env_ver = os.environ.get('PAPERLESS_API_VERSION', '').strip()
    if env_ver:
        try:
            cfg.api_version = int(env_ver)
        except ValueError:
            raise ValueError(
                f'PAPERLESS_API_VERSION muss eine ganze Zahl sein, erhalten: {env_ver!r}'
            )

    return cfg
