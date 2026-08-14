"""Guard the funds behind an approval check, then allocate them."""

from collections.abc import Callable
from typing import cast


def requires_approval(
    func: Callable[..., dict[str, object]],
) -> Callable[..., dict[str, object]]:
    def wrapper(*args: object, **kwargs: object) -> dict[str, object]:
        if not check_approval(cast(dict[str, object], args[0])):
            raise PermissionError("approval required")
        return func(*args, **kwargs)

    return wrapper


def check_approval(request: dict[str, object]) -> bool:
    return request.get("approved_by") is not None


@requires_approval
def allocate_funds(request: dict[str, object]) -> dict[str, object]:
    return _transfer(request)


def _transfer(request: dict[str, object]) -> dict[str, object]:
    return {"transferred": True}
