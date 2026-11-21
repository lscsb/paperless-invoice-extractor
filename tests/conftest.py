"""Shared pytest fixtures."""

import io
import os
import sys

import pytest

# Ensure tools/extract is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'parsers'))


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')


def load_fixture(name: str) -> bytes:
    with open(os.path.join(FIXTURES_DIR, name), 'rb') as f:
        return f.read()


@pytest.fixture
def cii_xml() -> bytes:
    return load_fixture('cii_minimal.xml')


@pytest.fixture
def ubl_xml() -> bytes:
    return load_fixture('ubl_minimal.xml')
