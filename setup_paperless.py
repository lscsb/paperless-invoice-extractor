"""Setup command: ensure required custom fields and tags exist in Paperless."""

from paperless_client import PaperlessClient
from extract_config import Config


def run_setup(client: PaperlessClient, cfg: Config, dry_run: bool = False) -> bool:
    """Ensure required fields and tags exist. Returns True if no errors."""
    ok = True
    existing_fields = {f['name']: f for f in client.get_custom_fields()}

    for field_spec in cfg.all_fields():
        name = field_spec['name']
        if name not in existing_fields:
            if dry_run:
                print(f'  [dry-run] würde anlegen: Feld "{name}" ({field_spec["data_type"]})')
            else:
                client.create_custom_field(
                    name=name,
                    data_type=field_spec['data_type'],
                    extra_data=field_spec.get('extra_data'),
                )
                print(f'  Feld angelegt: "{name}"')
        else:
            existing = existing_fields[name]
            if existing['data_type'] != field_spec['data_type']:
                print(
                    f'  WARNUNG: Feld "{name}" existiert mit Typ '
                    f'"{existing["data_type"]}", erwartet "{field_spec["data_type"]}" – nicht geändert'
                )
                ok = False
            elif name == cfg.field_data_source and 'extra_data' in field_spec:
                expected_opts = set(field_spec['extra_data']['select_options'])
                existing_opts = set((existing.get('extra_data') or {}).get('select_options', []))
                missing = expected_opts - existing_opts
                if missing:
                    print(
                        f'  WARNUNG: Feld "{name}" fehlen Optionen: '
                        f'{sorted(missing)} – nicht geändert'
                    )
                    ok = False
                else:
                    print(f'  Feld OK: "{name}"')
            else:
                print(f'  Feld OK: "{name}"')

    existing_tags = {t['name']: t for t in client.get_tags()}

    for tag_name in cfg.all_tags():
        if tag_name not in existing_tags:
            if dry_run:
                print(f'  [dry-run] würde anlegen: Tag "{tag_name}"')
            else:
                client.create_tag(tag_name)
                print(f'  Tag angelegt: "{tag_name}"')
        else:
            print(f'  Tag OK: "{tag_name}"')

    return ok
