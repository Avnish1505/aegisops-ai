"""Guard the funds behind an approval check, then allocate them."""


def requires_approval(func):
    def wrapper(*args, **kwargs):
        if not check_approval(args[0]):
            raise PermissionError("approval required")
        return func(*args, **kwargs)

    return wrapper


def check_approval(request):
    return request.get("approved_by") is not None


@requires_approval
def allocate_funds(request):
    return _transfer(request)


def _transfer(request):
    return {"transferred": True}
