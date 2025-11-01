"""Enumerations for Google Cloud regions."""

from __future__ import annotations

from enum import Enum
from typing import Tuple


class Region(Enum):
    """Canonical set of Google Cloud regions."""

    US_WEST1 = ("North America", "us-west1", "Oregon")
    US_WEST2 = ("North America", "us-west2", "Los Angeles")
    US_WEST3 = ("North America", "us-west3", "Salt Lake City")
    US_WEST4 = ("North America", "us-west4", "Las Vegas")
    US_CENTRAL1 = ("North America", "us-central1", "Iowa")
    US_CENTRAL2 = ("North America", "us-central2", "Oklahoma—private Google Cloud region")
    NORTHAMERICA_NORTHEAST1 = ("North America", "northamerica-northeast1", "Montréal")
    NORTHAMERICA_NORTHEAST2 = ("North America", "northamerica-northeast2", "Toronto")
    NORTHAMERICA_SOUTH1 = ("North America", "northamerica-south1", "Queretaro")
    US_EAST1 = ("North America", "us-east1", "South Carolina")
    US_EAST4 = ("North America", "us-east4", "Northern Virginia")
    US_EAST5 = ("North America", "us-east5", "Columbus")
    US_SOUTH1 = ("North America", "us-south1", "Dallas")
    SOUTHAMERICA_WEST1 = ("South America", "southamerica-west1", "Santiago")
    SOUTHAMERICA_EAST1 = ("South America", "southamerica-east1", "São Paulo")
    EUROPE_WEST2 = ("Europe", "europe-west2", "London")
    EUROPE_WEST1 = ("Europe", "europe-west1", "Belgium")
    EUROPE_WEST4 = ("Europe", "europe-west4", "Netherlands")
    EUROPE_WEST8 = ("Europe", "europe-west8", "Milan")
    EUROPE_SOUTHWEST1 = ("Europe", "europe-southwest1", "Madrid")
    EUROPE_WEST9 = ("Europe", "europe-west9", "Paris")
    EUROPE_WEST12 = ("Europe", "europe-west12", "Turin")
    EUROPE_WEST10 = ("Europe", "europe-west10", "Berlin")
    EUROPE_WEST3 = ("Europe", "europe-west3", "Frankfurt")
    EUROPE_NORTH1 = ("Europe", "europe-north1", "Finland")
    EUROPE_NORTH2 = ("Europe", "europe-north2", "Stockholm")
    EUROPE_CENTRAL2 = ("Europe", "europe-central2", "Warsaw")
    EUROPE_WEST6 = ("Europe", "europe-west6", "Zürich")
    ME_CENTRAL1 = ("Middle East", "me-central1", "Doha")
    ME_CENTRAL2 = ("Middle East", "me-central2", "Dammam")
    ME_WEST1 = ("Middle East", "me-west1", "Tel Aviv")
    ASIA_SOUTH1 = ("Asia", "asia-south1", "Mumbai")
    ASIA_SOUTH2 = ("Asia", "asia-south2", "Delhi")
    ASIA_SOUTHEAST1 = ("Asia", "asia-southeast1", "Singapore")
    ASIA_SOUTHEAST2 = ("Asia", "asia-southeast2", "Jakarta")
    ASIA_EAST2 = ("Asia", "asia-east2", "Hong Kong")
    ASIA_EAST1 = ("Asia", "asia-east1", "Taiwan")
    ASIA_NORTHEAST1 = ("Asia", "asia-northeast1", "Tokyo")
    ASIA_NORTHEAST2 = ("Asia", "asia-northeast2", "Osaka")
    ASIA_NORTHEAST3 = ("Asia", "asia-northeast3", "Seoul")
    AUSTRALIA_SOUTHEAST1 = ("Australia", "australia-southeast1", "Sydney")
    AUSTRALIA_SOUTHEAST2 = ("Australia", "australia-southeast2", "Melbourne")
    AFRICA_SOUTH1 = ("Africa", "africa-south1", "Johannesburg")

    def __init__(self, continent: str, region_id: str, description: str) -> None:
        self._continent = continent
        self._region_id = region_id
        self._description = description

    @property
    def continent(self) -> str:
        """Continent grouping for the region."""

        return self._continent

    @property
    def region_id(self) -> str:
        """Region identifier (e.g., ``us-west1``)."""

        return self._region_id

    @property
    def description(self) -> str:
        """Human-readable description for the region."""

        return self._description

    @classmethod
    def from_region_id(cls, region_id: str) -> "Region":
        """Return the enum entry matching ``region_id``."""

        normalized = region_id.lower()
        for region in cls:
            if region.region_id == normalized:
                return region
        raise ValueError(f"Unknown region id: {region_id!r}")


class MultiRegion(Enum):
    """Canonical set of Google Cloud multi-regions."""

    EUR3 = ("eur3", "Europe", (Region.EUROPE_WEST1, Region.EUROPE_WEST4), Region.EUROPE_NORTH1)
    NAM5 = (
        "nam5",
        "United States (Central)",
        (Region.US_CENTRAL1, Region.US_CENTRAL2),
        Region.US_EAST1,
    )
    NAM7 = (
        "nam7",
        "United States (Central and East)",
        (Region.US_CENTRAL1, Region.US_EAST4),
        Region.US_CENTRAL2,
    )

    def __init__(
        self,
        multi_region_id: str,
        description: str,
        read_write_regions: Tuple[Region, ...],
        witness_region: Region,
    ) -> None:
        self._multi_region_id = multi_region_id
        self._description = description
        self._read_write_regions = tuple(read_write_regions)
        self._witness_region = witness_region

    @property
    def multi_region_id(self) -> str:
        """Identifier for the multi-region (e.g., ``nam5``)."""

        return self._multi_region_id

    @property
    def description(self) -> str:
        """Human-readable description for the multi-region."""

        return self._description

    @property
    def read_write_regions(self) -> Tuple[Region, ...]:
        """Regions that accept read-write traffic."""

        return self._read_write_regions

    @property
    def witness_region(self) -> Region:
        """Witness region used for tie-breaking."""

        return self._witness_region

    @classmethod
    def from_multi_region_id(cls, multi_region_id: str) -> "MultiRegion":
        """Return the enum entry matching ``multi_region_id``."""

        normalized = multi_region_id.lower()
        for multi_region in cls:
            if multi_region.multi_region_id == normalized:
                return multi_region
        raise ValueError(f"Unknown multi-region id: {multi_region_id!r}")


__all__ = ["Region", "MultiRegion"]
