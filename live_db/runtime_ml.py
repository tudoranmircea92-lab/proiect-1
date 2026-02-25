"""ML runtime intentionally inactive in v1 (extraction-only release)."""


def train_or_predict(*_args, **_kwargs):
    raise NotImplementedError("ML runtime is intentionally disabled in v1.")
