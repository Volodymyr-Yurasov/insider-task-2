import pandas as pd
from django.db.models import QuerySet

# ORM path -> exported column name. `rating`..`popularity` come from `with_stats()`.
EXPORT_FIELDS = {
    "id": "id",
    "name": "name",
    "description": "description",
    "category__name": "category",
    "address": "address",
    "latitude": "latitude",
    "longitude": "longitude",
    "author__username": "author",
    "rating": "rating",
    "reviews_count": "reviews_count",
    "views_7d": "views_7d",
    "popularity": "popularity",
    "created_at": "created_at",
    "updated_at": "updated_at",
}

CONTENT_TYPES = {
    "csv": "text/csv; charset=utf-8",
    "json": "application/json",
}


def locations_to_dataframe(queryset: QuerySet) -> pd.DataFrame:
    rows = list(queryset.values(*EXPORT_FIELDS))
    df = pd.DataFrame.from_records(rows, columns=list(EXPORT_FIELDS)).rename(columns=EXPORT_FIELDS)
    df[["latitude", "longitude"]] = df[["latitude", "longitude"]].astype(float)
    df["rating"] = df["rating"].astype(float).round(2)
    df["popularity"] = df["popularity"].astype(float).round(3)
    for column in ("created_at", "updated_at"):
        df[column] = pd.to_datetime(df[column], utc=True).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return df


def export_locations(queryset: QuerySet, file_format: str) -> bytes:
    df = locations_to_dataframe(queryset)
    if file_format == "json":
        return df.to_json(orient="records", force_ascii=False, indent=2).encode()
    # BOM so Excel detects UTF-8 (Cyrillic names, etc.).
    return df.to_csv(index=False).encode("utf-8-sig")
