from demicode.codepoint import CodePoint
from demicode.property import BinaryProperty, Category, CharacterData, EastAsianWidth
from demicode.ucd import UCD

VERBOSE = True

EXPECTED_DATA = (
    CharacterData(
        codepoint=CodePoint.of(0x0023),
        category=Category.Other_Punctuation,
        east_asian_width=EastAsianWidth.Narrow,
        age='1.1',
        name='NUMBER SIGN',
        block='Basic Latin',
        flags=frozenset([BinaryProperty.Emoji, BinaryProperty.Emoji_Component])
    ),
    CharacterData(
        codepoint=CodePoint.of(0x26A1),
        category=Category.Other_Symbol,
        east_asian_width=EastAsianWidth.Wide,
        age='4.0',
        name='HIGH VOLTAGE SIGN',
        block='Miscellaneous Symbols',
        flags=frozenset([BinaryProperty.Emoji, BinaryProperty.Emoji_Presentation,
                         BinaryProperty.Extended_Pictographic])
    ),
    CharacterData(
        codepoint=CodePoint.of(0x2763),
        category=Category.Other_Symbol,
        east_asian_width=EastAsianWidth.Neutral,
        age='1.1',
        name='HEAVY HEART EXCLAMATION MARK ORNAMENT',
        block='Dingbats',
        flags=frozenset([BinaryProperty.Emoji, BinaryProperty.Extended_Pictographic])
    ),
    CharacterData(  # An unassigned code point that is an extended pictograph
        codepoint=CodePoint.of(0x1F2FF),
        category=Category.Unassigned,
        east_asian_width=EastAsianWidth.Neutral,
        age=None,
        name=None,
        block='Enclosed Ideographic Supplement',
        flags=frozenset([BinaryProperty.Extended_Pictographic])
    ),

)

EXPECTED_COUNTS = {
    BinaryProperty.Dash: 30,
    BinaryProperty.Emoji: 1424,
    BinaryProperty.Emoji_Component: 146,
    BinaryProperty.Emoji_Modifier: 5,
    BinaryProperty.Emoji_Modifier_Base: 134,
    BinaryProperty.Emoji_Presentation: 1205,
    BinaryProperty.Extended_Pictographic: 3537,
    BinaryProperty.Noncharacter_Code_Point: 66,
    BinaryProperty.Variation_Selector: 260,
    BinaryProperty.White_Space: 25,
}

def test_ucd() -> None:
    UCD.use_version('15.0.0')

    for expected_data in EXPECTED_DATA:
        actual_data = UCD.lookup(expected_data.codepoint)
        assert actual_data == expected_data,\
              f'Actual vs expected properties:\n{actual_data}\n{expected_data}'

    for property, expected_count in EXPECTED_COUNTS.items():
        actual_count = UCD.count_property(property)
        assert actual_count == expected_count,\
              f'Count {property.name} is {actual_count} but should be {expected_count}'

if __name__ == '__main__':
    test_ucd()
