"""Exploratory decoding of unescaped KWB payloads."""


def decode_temperature(byte_1, byte_2):
    """Decode a signed big-endian temperature in tenths of a degree."""
    value = (byte_1 << 8) + byte_2
    if value == 1300:
        return None
    if value > 32767:
        value -= 65536
    return value / 10


def decode_pairs(message_id, packet):
    """Try temperature, pressure, speed, and duration at both alignments.

    messages.csv specifies unsigned pressure (0.001 mbar/count), speed
    (0.6 rpm/count), and duration (10 ms/count). Only temperature uses
    signed values and the unavailable sentinel.
    """
    for start in (3, 4):
        yield "ID %d two-byte decode from offset %d:" % (message_id, start)
        for offset in range(start, len(packet) - 1, 2):
            raw = int.from_bytes(packet[offset:offset + 2], 'big', signed=True)
            unsigned = int.from_bytes(packet[offset:offset + 2], 'big')
            value = decode_temperature(packet[offset], packet[offset + 1])
            yield "  Offset %d: raw=%d temperature=%s mbar=%s rpm=%s ms=%d" % (
                offset, raw, value, round(unsigned * 0.001, 10),
                round(unsigned * 0.6, 10), unsigned * 10)
