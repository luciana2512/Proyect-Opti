def _safe_round(x, ndigits):
    """Round a value after coercing to float when possible; return original on failure.

    Use this to avoid static type-checker warnings about `round` overloads.
    """
    try:
        return round(float(x), ndigits)
    except Exception:
        return x
