"""Standard API envelope.

Every endpoint returns `{success, data, error}` so the frontend has exactly one
response shape to handle, and errors never leak internals.
"""

from typing import Any, Generic, List, Optional, TypeVar

from pydantic import BaseModel

DataT = TypeVar("DataT")


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[Any] = None


class StandardResponse(BaseModel, Generic[DataT]):
    success: bool = True
    data: Optional[DataT] = None
    error: Optional[ErrorDetail] = None


class PaginatedData(BaseModel, Generic[DataT]):
    items: List[DataT]
    page: int
    page_size: int
    total_items: int
    total_pages: int
    has_next: bool
    has_previous: bool


class PaginatedResponse(StandardResponse[PaginatedData[DataT]], Generic[DataT]):
    pass


def paginate(
    items: List[Any], page: int, page_size: int, total_items: int
) -> dict:
    """Build a paginated envelope from a page of items and the true total.

    `total_items` must be a real COUNT, not `len(items)` -- deriving it from the
    page makes `has_next` permanently false.
    """
    total_pages = max(1, -(-total_items // page_size)) if total_items else 0
    return {
        "success": True,
        "data": {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total_items": total_items,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_previous": page > 1,
        },
    }
