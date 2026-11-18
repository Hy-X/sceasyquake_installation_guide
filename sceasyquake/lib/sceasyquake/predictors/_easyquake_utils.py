"""Shared key normalization helpers for EasyQuake subprocess predictors."""
from __future__ import annotations

from typing import Dict, Iterable, Optional, Tuple


def normalize_nsl_key(key, stream=None) -> Tuple[str, str, str]:
    """Normalize a stream key into a ``(network, station, location)`` 3-tuple.

    Accepts:
    - 3-tuples/lists ``(net, sta, loc)`` (or longer sequences, taking first 3)
    - 2-tuples/lists ``(net, sta)`` -> ``(net, sta, '')``
    - Dot-delimited strings like ``'NET.STA.LOC'`` (from ``StreamWorker``) or
      ``'NET.STA.LOC.CHA'`` -> ``(parts[0], parts[1], parts[2])``
    - Single strings or 1-tuples, falling back to ``stream[0].stats`` when
      available.
    """
    if isinstance(key, (tuple, list)):
        if len(key) >= 3:
            return (str(key[0]), str(key[1]), str(key[2]))
        if len(key) == 2:
            return (str(key[0]), str(key[1]), '')
        key_str = str(key[0]) if len(key) == 1 else ''
    elif isinstance(key, str):
        parts = key.split('.')
        if len(parts) >= 3:
            return (parts[0], parts[1], parts[2])
        if len(parts) == 2:
            return (parts[0], parts[1], '')
        key_str = key
    else:
        key_str = str(key)

    if stream is not None:
        try:
            if len(stream) > 0 and hasattr(stream[0], 'stats'):
                st_stats = stream[0].stats
                return (
                    str(getattr(st_stats, 'network', '')),
                    str(getattr(st_stats, 'station', key_str)),
                    str(getattr(st_stats, 'location', '')),
                )
        except Exception:
            pass
    return ('', key_str, '')


def collect_nsl_streams(
    keys_and_streams: Iterable[Tuple[object, object]],
) -> Dict[Tuple[str, str, str], object]:
    """Build a ``{(net, sta, loc): stream}`` mapping from ``predict_multi`` pairs.

    Streams that resolve to the same ``(net, sta, loc)`` (for example,
    per-channel keys ``'TX.A..HHZ'`` and ``'TX.A..HHN'``) are merged rather
    than overwriting one another.
    """
    streams: Dict[Tuple[str, str, str], object] = {}
    for key, st in keys_and_streams:
        nsl = normalize_nsl_key(key, st)
        if nsl in streams:
            streams[nsl] = streams[nsl] + st
        else:
            streams[nsl] = st
    return streams


def record_station_location(
    loc_by_ns: Dict[Tuple[str, str], Optional[str]],
    net: str,
    sta: str,
    loc: str,
) -> None:
    """Record location code for ``(net, sta)``; mark ``None`` if ambiguous."""
    ns = (net, sta)
    if ns not in loc_by_ns:
        loc_by_ns[ns] = loc
    elif loc_by_ns[ns] != loc:
        loc_by_ns[ns] = None
