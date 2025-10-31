"""Unit tests for lookup_api using the bundled API map.

These tests avoid mocks and do not hit the network.
"""

import pytest

from pdum.gcp.admin import APIResolutionError, lookup_api


def test_lookup_exact_match_compute_engine():
    assert lookup_api("Compute Engine API") == "compute.googleapis.com"


def test_lookup_exact_match_unique():
    # Use an early, unique-looking entry to reduce ambiguity
    assert (
        lookup_api("Abusive Experience Report API")
        == "abusiveexperiencereport.googleapis.com"
    )


def test_lookup_ambiguous_short_term_raises():
    # Many APIs contain the word "API" or "Storage"; should raise
    with pytest.raises(APIResolutionError):
        lookup_api("API")


def test_lookup_no_match_raises():
    with pytest.raises(APIResolutionError):
        lookup_api("ThisDoesNotExist12345")


def test_lookup_repeated_is_stable():
    a = lookup_api("Compute Engine API")
    b = lookup_api("Compute Engine API")
    assert a == b
