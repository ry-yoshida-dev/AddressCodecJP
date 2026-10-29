class AddressCodecError(Exception):
    """
    Base class of the errors raised by AddressCodecJP.

    Each subclass also derives from the most specific built-in exception, so callers may
    catch either this hierarchy or the built-in one.
    """
