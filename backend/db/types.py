"""Column types that differ between PostgreSQL (PostGIS) and the SQLite used by tests."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import String, func
from sqlalchemy.engine import Dialect
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.types import TypeDecorator, TypeEngine, UserDefinedType

_POINT = re.compile(r"POINT\s*\(\s*(-?[\d.eE+-]+)\s+(-?[\d.eE+-]+)\s*\)", re.IGNORECASE)


class _Geography(UserDefinedType[str]):
    """PostGIS geography(Point, 4326); values travel as EWKT text."""

    cache_ok = True

    def get_col_spec(self, **kw: Any) -> str:
        return "geography(Point,4326)"

    # Keep the outer column type (GeoPoint) on both expressions so its tuple <-> EWKT conversion
    # still runs; typing them as _Geography would hand raw WKT strings back to callers.
    def bind_expression(self, bindvalue: Any) -> ColumnElement[Any]:
        return func.ST_GeogFromText(bindvalue, type_=bindvalue.type)

    def column_expression(self, col: Any) -> ColumnElement[Any]:
        return func.ST_AsText(col, type_=col.type)


class GeoPoint(TypeDecorator[tuple[float, float]]):
    """A WGS84 point as ``(lat, lon)`` in Python.

    PostgreSQL stores it as PostGIS ``geography(Point,4326)`` (so distance queries are in metres);
    other dialects store the same EWKT text in a string column.
    """

    impl = String(96)
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect) -> TypeEngine[Any]:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(_Geography())
        return dialect.type_descriptor(String(96))

    def process_bind_param(self, value: Any, dialect: Dialect) -> str | None:
        if value is None:
            return None
        lat, lon = value
        return f"SRID=4326;POINT({float(lon)!r} {float(lat)!r})"

    def process_result_value(self, value: Any, dialect: Dialect) -> tuple[float, float] | None:
        if value is None:
            return None
        match = _POINT.search(str(value))
        if match is None:
            raise ValueError(f"not a WKT point: {value!r}")
        lon, lat = float(match.group(1)), float(match.group(2))
        return (lat, lon)
