"""Paperless-ngx REST API client."""

import requests


class PaperlessError(Exception):
    def __init__(self, message: str, status_code: int = 0):
        super().__init__(message)
        self.status_code = status_code


class PaperlessClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Token {token}',
            'Accept': 'application/json; version=5',
        })

    def _get(self, path: str, **kwargs) -> dict | list:
        url = f'{self.base_url}{path}'
        resp = self.session.get(url, **kwargs)
        if not resp.ok:
            raise PaperlessError(f'GET {path} failed: {resp.status_code}', resp.status_code)
        return resp.json()

    def _post(self, path: str, json: dict) -> dict:
        url = f'{self.base_url}{path}'
        resp = self.session.post(url, json=json)
        if not resp.ok:
            raise PaperlessError(f'POST {path} failed: {resp.status_code}', resp.status_code)
        return resp.json()

    def _patch(self, path: str, json: dict) -> dict:
        url = f'{self.base_url}{path}'
        resp = self.session.patch(url, json=json)
        if not resp.ok:
            raise PaperlessError(f'PATCH {path} failed: {resp.status_code}', resp.status_code)
        return resp.json()

    def get_documents(self, tag_ids: list[int] | None = None,
                      exclude_tag_ids: list[int] | None = None,
                      page_size: int = 100) -> list[dict]:
        """Return all documents (handles pagination)."""
        params = {'page_size': page_size, 'page': 1}
        if tag_ids:
            params['tags__id__all'] = ','.join(str(t) for t in tag_ids)
        if exclude_tag_ids:
            params['tags__id__none'] = ','.join(str(t) for t in exclude_tag_ids)

        results = []
        while True:
            data = self._get('/api/documents/', params=params)
            results.extend(data.get('results', []))
            if not data.get('next'):
                break
            params['page'] += 1
        return results

    def get_document(self, doc_id: int) -> dict:
        return self._get(f'/api/documents/{doc_id}/')

    def download_document(self, doc_id: int) -> bytes:
        """Download original PDF bytes."""
        url = f'{self.base_url}/api/documents/{doc_id}/download/?original=true'
        resp = self.session.get(url)
        if not resp.ok:
            raise PaperlessError(f'Download {doc_id} failed: {resp.status_code}', resp.status_code)
        return resp.content

    def get_tags(self) -> list[dict]:
        """Return list of {id, name, ...}."""
        data = self._get('/api/tags/?page_size=1000')
        return data.get('results', [])

    def create_tag(self, name: str, colour: int | None = None) -> dict:
        payload = {'name': name}
        if colour is not None:
            payload['colour'] = colour
        return self._post('/api/tags/', json=payload)

    def get_custom_fields(self) -> list[dict]:
        """Return list of {id, name, data_type, extra_data}."""
        data = self._get('/api/custom_fields/?page_size=1000')
        return data.get('results', [])

    def create_custom_field(self, name: str, data_type: str,
                            extra_data: dict | None = None) -> dict:
        payload = {'name': name, 'data_type': data_type}
        if extra_data is not None:
            payload['extra_data'] = extra_data
        return self._post('/api/custom_fields/', json=payload)

    def patch_document(self, doc_id: int,
                       tags: list[int] | None = None,
                       custom_fields: list[dict] | None = None) -> dict:
        """Read-merge-patch: GET current state, merge, then PATCH."""
        current = self.get_document(doc_id)

        # Merge tags by ID (additive)
        existing_tags = list(current.get('tags', []))
        if tags:
            for tag_id in tags:
                if tag_id not in existing_tags:
                    existing_tags.append(tag_id)

        # Merge custom_fields by field ID
        existing_fields = {cf['field']: cf['value'] for cf in current.get('custom_fields', [])}
        if custom_fields:
            for cf in custom_fields:
                existing_fields[cf['field']] = cf['value']

        payload = {
            'tags': existing_tags,
            'custom_fields': [{'field': k, 'value': v} for k, v in existing_fields.items()],
        }
        return self._patch(f'/api/documents/{doc_id}/', json=payload)
