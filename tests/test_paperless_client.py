"""Tests for PaperlessClient: API versioning, 406 handling, Accept header."""

import os
import sys

import pytest
import responses as responses_lib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from paperless_client import PaperlessClient, PaperlessError, PaperlessVersionError

PAPERLESS_URL = 'http://paperless.test'
TOKEN = 'testtoken'


def make_client(api_version: int = 10):
    return PaperlessClient(base_url=PAPERLESS_URL, token=TOKEN, api_version=api_version)


# ---------------------------------------------------------------------------
# Accept header
# ---------------------------------------------------------------------------

@responses_lib.activate
def test_accept_header_v10():
    """Client sends Accept: application/json; version=10 by default."""
    responses_lib.add(responses_lib.GET, f'{PAPERLESS_URL}/api/documents/',
                      json={'results': [], 'next': None})
    make_client(api_version=10).get_documents()
    req = responses_lib.calls[0].request
    assert req.headers['Accept'] == 'application/json; version=10'


@responses_lib.activate
def test_accept_header_custom_version():
    """api_version param is reflected in the Accept header."""
    responses_lib.add(responses_lib.GET, f'{PAPERLESS_URL}/api/documents/',
                      json={'results': [], 'next': None})
    make_client(api_version=9).get_documents()
    req = responses_lib.calls[0].request
    assert req.headers['Accept'] == 'application/json; version=9'


# ---------------------------------------------------------------------------
# HTTP 406 — version not supported
# ---------------------------------------------------------------------------

@responses_lib.activate
def test_406_raises_version_error_with_server_version():
    """HTTP 406 with X-Api-Version header → PaperlessVersionError with server version."""
    responses_lib.add(
        responses_lib.GET,
        f'{PAPERLESS_URL}/api/documents/',
        status=406,
        headers={'X-Api-Version': '10'},
        json={'detail': 'Invalid version in "Accept" header.'},
    )
    client = make_client(api_version=5)
    with pytest.raises(PaperlessVersionError) as exc_info:
        client.get_documents()

    err = exc_info.value
    assert err.status_code == 406
    assert err.requested_version == 5
    assert err.server_version == '10'
    assert '5' in str(err)
    assert '10' in str(err)


@responses_lib.activate
def test_406_raises_version_error_without_server_version():
    """HTTP 406 without X-Api-Version header → PaperlessVersionError with server_version=None."""
    responses_lib.add(
        responses_lib.GET,
        f'{PAPERLESS_URL}/api/tags/?page_size=1000',
        status=406,
    )
    client = make_client(api_version=3)
    with pytest.raises(PaperlessVersionError) as exc_info:
        client.get_tags()

    err = exc_info.value
    assert err.status_code == 406
    assert err.server_version is None
    assert '3' in str(err)


@responses_lib.activate
def test_406_on_post_raises_version_error():
    """POST endpoints also raise PaperlessVersionError on 406."""
    responses_lib.add(
        responses_lib.POST,
        f'{PAPERLESS_URL}/api/tags/',
        status=406,
        headers={'X-Api-Version': '10'},
    )
    client = make_client(api_version=5)
    with pytest.raises(PaperlessVersionError) as exc_info:
        client.create_tag('TestTag')
    assert exc_info.value.server_version == '10'


@responses_lib.activate
def test_406_on_patch_raises_version_error():
    """PATCH endpoints also raise PaperlessVersionError on 406."""
    responses_lib.add(
        responses_lib.GET,
        f'{PAPERLESS_URL}/api/documents/1/',
        json={'id': 1, 'tags': [], 'custom_fields': []},
    )
    responses_lib.add(
        responses_lib.PATCH,
        f'{PAPERLESS_URL}/api/documents/1/',
        status=406,
        headers={'X-Api-Version': '10'},
    )
    client = make_client(api_version=5)
    with pytest.raises(PaperlessVersionError):
        client.patch_document(1, tags=[42])


# ---------------------------------------------------------------------------
# Non-406 errors still raise plain PaperlessError
# ---------------------------------------------------------------------------

@responses_lib.activate
def test_non_406_raises_plain_error():
    """HTTP 500 raises PaperlessError (not PaperlessVersionError)."""
    responses_lib.add(
        responses_lib.GET,
        f'{PAPERLESS_URL}/api/documents/',
        status=500,
    )
    with pytest.raises(PaperlessError) as exc_info:
        make_client().get_documents()
    assert not isinstance(exc_info.value, PaperlessVersionError)
    assert exc_info.value.status_code == 500


# ---------------------------------------------------------------------------
# create_custom_field: select_options format normalisation
# ---------------------------------------------------------------------------

@responses_lib.activate
def test_create_select_field_v10_converts_strings_to_dicts():
    """API v7+: string select_options are converted to {label} dicts before POST."""
    responses_lib.add(responses_lib.POST, f'{PAPERLESS_URL}/api/custom_fields/',
                      json={'id': 9, 'name': 'Quelle', 'data_type': 'select',
                            'extra_data': {'select_options': [
                                {'id': 'abc', 'label': 'A'}, {'id': 'def', 'label': 'B'}
                            ]}})
    make_client(api_version=10).create_custom_field(
        name='Quelle', data_type='select',
        extra_data={'select_options': ['A', 'B']},
    )
    import json as _json
    body = _json.loads(responses_lib.calls[0].request.body)
    assert body['extra_data']['select_options'] == [{'label': 'A'}, {'label': 'B'}]


@responses_lib.activate
def test_create_select_field_v5_keeps_strings():
    """API v5/v6: string select_options are sent as-is."""
    responses_lib.add(responses_lib.POST, f'{PAPERLESS_URL}/api/custom_fields/',
                      json={'id': 9, 'name': 'Quelle', 'data_type': 'select', 'extra_data': {}})
    make_client(api_version=5).create_custom_field(
        name='Quelle', data_type='select',
        extra_data={'select_options': ['A', 'B']},
    )
    import json as _json
    body = _json.loads(responses_lib.calls[0].request.body)
    assert body['extra_data']['select_options'] == ['A', 'B']


@responses_lib.activate
def test_create_select_field_v10_already_dicts_unchanged():
    """If options are already dicts, they are forwarded unchanged."""
    responses_lib.add(responses_lib.POST, f'{PAPERLESS_URL}/api/custom_fields/',
                      json={'id': 9, 'name': 'Quelle', 'data_type': 'select', 'extra_data': {}})
    opts = [{'id': 'abc', 'label': 'A'}]
    make_client(api_version=10).create_custom_field(
        name='Quelle', data_type='select',
        extra_data={'select_options': opts},
    )
    import json as _json
    body = _json.loads(responses_lib.calls[0].request.body)
    assert body['extra_data']['select_options'] == opts


# ---------------------------------------------------------------------------
# PaperlessVersionError is a subclass of PaperlessError
# ---------------------------------------------------------------------------

def test_version_error_is_subclass():
    err = PaperlessVersionError(requested_version=5, server_version='10')
    assert isinstance(err, PaperlessError)
