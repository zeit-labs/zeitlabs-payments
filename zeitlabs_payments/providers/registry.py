from .payfort.processor import PayFort

PROCESSORS = {
    PayFort.SLUG: PayFort
}


def get_processor(slug: str):
    """
    Return an *instance* of the processor that matches `slug`
    or raise KeyError if unknown.
    """
    try:
        return PROCESSORS[slug]()
    except KeyError:
        raise ValueError(f"Unsupported payment provider: {slug!r}")