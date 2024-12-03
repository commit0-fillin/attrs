from functools import total_ordering
from ._funcs import astuple
from ._make import attrib, attrs

@total_ordering
@attrs(eq=False, order=False, slots=True, frozen=True)
class VersionInfo:
    """
    A version object that can be compared to tuple of length 1--4:

    >>> attr.VersionInfo(19, 1, 0, "final")  <= (19, 2)
    True
    >>> attr.VersionInfo(19, 1, 0, "final") < (19, 1, 1)
    True
    >>> vi = attr.VersionInfo(19, 2, 0, "final")
    >>> vi < (19, 1, 1)
    False
    >>> vi < (19,)
    False
    >>> vi == (19, 2,)
    True
    >>> vi == (19, 2, 1)
    False

    .. versionadded:: 19.2
    """
    year = attrib(type=int)
    minor = attrib(type=int)
    micro = attrib(type=int)
    releaselevel = attrib(type=str)

    @classmethod
    def _from_version_string(cls, s):
        """
        Parse *s* and return a _VersionInfo.
        """
        parts = s.split('.')
        if len(parts) < 3:
            raise ValueError("Version string must have at least 3 components")
        year, minor, micro = map(int, parts[:3])
        releaselevel = parts[3] if len(parts) > 3 else "final"
        return cls(year, minor, micro, releaselevel)

    def _ensure_tuple(self, other):
        """
        Ensure *other* is a tuple of a valid length.

        Returns a possibly transformed *other* and ourselves as a tuple of
        the same length as *other*.
        """
        if not isinstance(other, tuple):
            raise NotImplementedError(f"Cannot compare VersionInfo to {type(other)}")
        
        if len(other) > 4:
            raise ValueError("Comparison tuple too long")
        
        self_tuple = (self.year, self.minor, self.micro, self.releaselevel)
        other_tuple = other + (None,) * (4 - len(other))
        
        return self_tuple[:len(other)], other_tuple

    def __eq__(self, other):
        try:
            us, them = self._ensure_tuple(other)
        except NotImplementedError:
            return NotImplemented
        return us == them

    def __lt__(self, other):
        try:
            us, them = self._ensure_tuple(other)
        except NotImplementedError:
            return NotImplemented
        return us < them
