"""Code points selected by human judgement."""

from .codepoint import CodePoint, CodePointSequence

__all__ = (
    'ARROWS',
    'LINGCHI',
    'MAD_DASH',
    'TASTE_OF_EMOJI',
    'VERSION_ORACLE',
)

def _prep(text: str) -> str | CodePoint | CodePointSequence:
    if text[0] == '\u0001':
        return text
    if len(text) == 1:
        return CodePoint.of(text)
    return CodePointSequence.from_string(text)

ARROWS = tuple(_prep(text) for text in (
    '\u0001An Arrow’s Flight',
    '\u2190', # leftwards arrow
    '\u27F5', # long leftwards arrow
    '\u2192', # rightwards arrow
    '\u27F6', # long rightwards arrow
    '\u2194', # left right arrow
    '\u27F7', # long left right arrow
    '\u21D0', # leftwards double arrow
    '\u27F8', # long leftwards double arrow
    '\u21D2', # rightwards double arrow
    '\u27F9', # long rightwards double arrow
    '\u21D4', # left right double arrow
    '\u27FA', # long left right double arrow
    '\u21A4', # leftwards arrow from bar
    '\u27FB', # long leftwards arrow from bar
    '\u21A6', # rightwards arrow from bar
    '\u27FC', # long rightwards arrow from bar
    '\u2906', # leftwards double arrow from bar
    '\u27FD', # long leftwards double arrow from bar
    '\u2907', # rightwards double arrow from bar
    '\u27FE', # long rightwards double arrow from bar
    '\u21DC', # leftwards squiggle arrow
    '\u2B33', # long leftwards squiggle arrow
    '\u21DD', # rightwards squiggle arrow
    '\u27FF', # long rightwards squiggle arrow
))

LINGCHI = tuple(_prep(text) for text in (
    '\u0001Death by a Thousand Cuts',
    '\u200B',      # ZERO WIDTH SPACE
    ' ',           # SPACE
    '\u2588',      # FULL BLOCK
    '\u2042',      # ASTERISM
    '\u2234',      # THEREFORE
    '\u0B83',      # TAMIL SIGN VISARGA
    '\u2032',      # PRIME
    '\u2033',      # DOUBLE PRIME
    '\u2034',      # TRIPLE PRIME
    '\u2057',      # QUADRUPLE PRIME
    '%',
    '‰',
    '‱',
    '℃',
    '∫',
    '∬',
    '∭',
    '⨌',
    '\u21A6',      # rightwards arrow from bar
    '\u27FC',      # long rightwards arrow from bar
    '♀︎',
    '⚢',
    '♋︎',
    '凌',          # https://en.wikipedia.org/wiki/Lingchi
    '遲',
    '!',
    '\uFF01',      # FULLWIDTH EXCLAMATION MARK
    '\u2755',      # WHITE EXCLAMATION MARK ORNAMENT
    '\u2757',      # HEAVY EXCLAMATION MARK SYMBOL
    '\u2763',      # HEART HEART EXCLAMATION MARK ORNAMENT
    '#',           # NUMBER SIGN (Emoji 2.0, not part of Unicode update)
))

MAD_DASH = tuple(_prep(text) for text in (
    '\u0001A Mad Dash',
    '-',           # HYPHEN-MINUS
    '\u2212',      # MINUS SIGN
    '\u2013',      # EN DASH
    '\u2014',      # EM DASH
    '\uFF0D',      # FULLWIDTH HYPHEN-MINUS
    '\u2E3A',      # TWO EM DASH
    '\u2E3B',      # THREE EM DASH
))

TASTE_OF_EMOJI = tuple(_prep(text) for text in (
    # Unicode versions 1.1, 3.2, 4.0, 4.1, 5.1, 5.2, 6.0, 7.0
    # Emoji versions 0.6, 0.7, 1.0, 2.0, 11.0
    '\u0001A Taste of Emoji',
    '\u26a1',                             # HIGH VOLTAGE        E0.6  4.0
    '\u2692',                             # HAMMER AND PICK     E1.0  4.1
    '\U0001F3DD',                         # DESERT ISLAND       E0.7  7.0
    '\U0001F596',                         # VULCAN SALUTE       E1.0  7.0
    '\U0001F9D1\u200D\U0001F4BB',         # technologist
    '\U0001F9D1\u200D\U0001F9B0',         # person: red hair
    '\U0001F3F3\uFE0F\u200D\U0001F308',   # rainbow flag
    '\U0001F1E9\U0001F1EA',               # flag: Germany
    '\U0001F442\U0001F3FE',               # ear: medium-dark skin tone
))

VERSION_ORACLE = tuple(_prep(text) for text in (
    '\u0001Emoji Version Oracle', # Comprising Emoji with Wide as East Asian Width
    # Nothing for 3.0 nor for 3.1
    '\u303D',      # PART ALTERNATION MARK, 3.2
    '\u26A1',      # HIGH VOLTAGE, 4.0
    '\u2693',      # ANCHOR, 4.1
    # Nothing for 5.0
    '\u2B50',      # STAR, 5.1
    '\u26D4',      # NO ENTRY, 5.2
    '\u23E9',      # BLACK RIGHT-POINTING DOUBLE TRIANGLE 6.0
    '\u23ED',      # BLACK RIGHT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR 6.0
    '\U0001F62C',  # GRIMACING FACE, 6.1
    '\U0001F596',  # VULCAN SALUTE, 7.0
    '\U0001F3DD',  # DESERT ISLAND, 7.0
    '\U0001F918',  # SIGN OF THE HORNS, 8.0 (Emoji 1.0, covering Unicode 1.1--8.0)
    # Emoji 2.0?
    '\U0001F991',  # SQUID, 9.0 (Emoji 3.0)
    # Emoji 4.0 added new ZWJ sequences only
    '\U0001F9DB',  # VAMPIRE, 10.0 (Emoji 5.0)
    # There are no Emoji 6--10. Versions align with Unicode thereafter
    '\U0001F973',  # PARTYING FACE, 11.0
    '\U0001F9A9',  # FLAMINGO, 12.0
    # 12.1 added new ZWJ sequences only and wasn't part of Unicode update
    '\U0001FA86',  # NESTING DOLLS, 13.0
    # 13.1 added new ZWJ sequences only and wasn't part of Unicode update
    '\U0001FAA9',  # MIRROR BALL, 14.0
    '\U0001FAE8',  # SHAKING FACE, 15.0
))

_EXTRA_TEST_POINTS = tuple(CodePoint.of(cp) for cp in (
    '\u0BF5', # TAMIL YEAR SIGN
    '\u0BF8', # TAMIL AS ABOVE SIGN
    ' ',
    '\u102A', # MYANMAR LETTER AU
    ' ',
    '\uA9C5', # JAVANESE PADA LUHUR
    ' ',
    '\uFDFD', # ARABIC LIGATURE BISMILLAH AR-RAHMAN AR-RAHEEM
    ' ',
    '\uFF23', # FULLWIDTH LATIN CAPITAL LETTER C
    '🟆',
    ' ',
    '\U00012219', # CUNEIFORM SIGN LUGAL OPPOSING LUGAL
    ' ',
    '\U0001242B', # CUNEIFORM NUMERIC SIGN NINE SHAR2
    ' ',
    '\U000130B8', # EGYPTIAN HIEROGLYPH D052
))
