# This module is machine-generated. Do not edit by hand.

from enum import IntEnum, StrEnum


__all__ = (
    "Property",
    "Age",
    "Block",
    "BLK",
    "Canonical_Combining_Class",
    "CCC",
    "Default_Ignorable_Code_Point",
    "DI",
    "East_Asian_Width",
    "EA",
    "Emoji",
    "Emoji_Component",
    "EComp",
    "Emoji_Modifier",
    "EMod",
    "Emoji_Modifier_Base",
    "EBase",
    "Emoji_Presentation",
    "EPres",
    "Extended_Pictographic",
    "ExtPict",
    "General_Category",
    "GC",
    "Indic_Conjunct_Break",
    "InCB",
    "Indic_Syllabic_Category",
    "InSC",
    "Script",
    "SC",
    "White_Space",
    "WSpace",
)


class Property:
    """Marker class for enumerations representing Unicode properties."""
    @property
    def label(self) -> str:
        return self.name # type: ignore


class Age(Property, StrEnum):
    V1_1 = "1.1"
    V2_0 = "2.0"
    V2_1 = "2.1"
    V3_0 = "3.0"
    V3_1 = "3.1"
    V3_2 = "3.2"
    V4_0 = "4.0"
    V4_1 = "4.1"
    V5_0 = "5.0"
    V5_1 = "5.1"
    V5_2 = "5.2"
    V6_0 = "6.0"
    V6_1 = "6.1"
    V6_2 = "6.2"
    V6_3 = "6.3"
    V7_0 = "7.0"
    V8_0 = "8.0"
    V9_0 = "9.0"
    V10_0 = "10.0"
    V11_0 = "11.0"
    V12_0 = "12.0"
    V12_1 = "12.1"
    V13_0 = "13.0"
    V14_0 = "14.0"
    V15_0 = "15.0"
    V15_1 = "15.1"
    Unassigned = "NA"


class Block(Property, StrEnum):
    Adlam = "Adlam"
    Aegean_Numbers = "Aegean_Numbers"
    Ahom = "Ahom"
    Alchemical_Symbols = "Alchemical"
    Alphabetic_Presentation_Forms = "Alphabetic_PF"
    Anatolian_Hieroglyphs = "Anatolian_Hieroglyphs"
    Ancient_Greek_Musical_Notation = "Ancient_Greek_Music"
    Ancient_Greek_Numbers = "Ancient_Greek_Numbers"
    Ancient_Symbols = "Ancient_Symbols"
    Arabic = "Arabic"
    Arabic_Extended_A = "Arabic_Ext_A"
    Arabic_Extended_B = "Arabic_Ext_B"
    Arabic_Extended_C = "Arabic_Ext_C"
    Arabic_Mathematical_Alphabetic_Symbols = "Arabic_Math"
    Arabic_Presentation_Forms_A = "Arabic_PF_A"
    Arabic_Presentation_Forms_B = "Arabic_PF_B"
    Arabic_Supplement = "Arabic_Sup"
    Armenian = "Armenian"
    Arrows = "Arrows"
    Basic_Latin = "ASCII"
    Avestan = "Avestan"
    Balinese = "Balinese"
    Bamum = "Bamum"
    Bamum_Supplement = "Bamum_Sup"
    Bassa_Vah = "Bassa_Vah"
    Batak = "Batak"
    Bengali = "Bengali"
    Bhaiksuki = "Bhaiksuki"
    Block_Elements = "Block_Elements"
    Bopomofo = "Bopomofo"
    Bopomofo_Extended = "Bopomofo_Ext"
    Box_Drawing = "Box_Drawing"
    Brahmi = "Brahmi"
    Braille_Patterns = "Braille"
    Buginese = "Buginese"
    Buhid = "Buhid"
    Byzantine_Musical_Symbols = "Byzantine_Music"
    Carian = "Carian"
    Caucasian_Albanian = "Caucasian_Albanian"
    Chakma = "Chakma"
    Cham = "Cham"
    Cherokee = "Cherokee"
    Cherokee_Supplement = "Cherokee_Sup"
    Chess_Symbols = "Chess_Symbols"
    Chorasmian = "Chorasmian"
    CJK_Unified_Ideographs = "CJK"
    CJK_Compatibility = "CJK_Compat"
    CJK_Compatibility_Forms = "CJK_Compat_Forms"
    CJK_Compatibility_Ideographs = "CJK_Compat_Ideographs"
    CJK_Compatibility_Ideographs_Supplement = "CJK_Compat_Ideographs_Sup"
    CJK_Unified_Ideographs_Extension_A = "CJK_Ext_A"
    CJK_Unified_Ideographs_Extension_B = "CJK_Ext_B"
    CJK_Unified_Ideographs_Extension_C = "CJK_Ext_C"
    CJK_Unified_Ideographs_Extension_D = "CJK_Ext_D"
    CJK_Unified_Ideographs_Extension_E = "CJK_Ext_E"
    CJK_Unified_Ideographs_Extension_F = "CJK_Ext_F"
    CJK_Unified_Ideographs_Extension_G = "CJK_Ext_G"
    CJK_Unified_Ideographs_Extension_H = "CJK_Ext_H"
    CJK_Unified_Ideographs_Extension_I = "CJK_Ext_I"
    CJK_Radicals_Supplement = "CJK_Radicals_Sup"
    CJK_Strokes = "CJK_Strokes"
    CJK_Symbols_And_Punctuation = "CJK_Symbols"
    Hangul_Compatibility_Jamo = "Compat_Jamo"
    Control_Pictures = "Control_Pictures"
    Coptic = "Coptic"
    Coptic_Epact_Numbers = "Coptic_Epact_Numbers"
    Counting_Rod_Numerals = "Counting_Rod"
    Cuneiform = "Cuneiform"
    Cuneiform_Numbers_And_Punctuation = "Cuneiform_Numbers"
    Currency_Symbols = "Currency_Symbols"
    Cypriot_Syllabary = "Cypriot_Syllabary"
    Cypro_Minoan = "Cypro_Minoan"
    Cyrillic = "Cyrillic"
    Cyrillic_Extended_A = "Cyrillic_Ext_A"
    Cyrillic_Extended_B = "Cyrillic_Ext_B"
    Cyrillic_Extended_C = "Cyrillic_Ext_C"
    Cyrillic_Extended_D = "Cyrillic_Ext_D"
    Cyrillic_Supplement = "Cyrillic_Sup"
    Deseret = "Deseret"
    Devanagari = "Devanagari"
    Devanagari_Extended = "Devanagari_Ext"
    Devanagari_Extended_A = "Devanagari_Ext_A"
    Combining_Diacritical_Marks = "Diacriticals"
    Combining_Diacritical_Marks_Extended = "Diacriticals_Ext"
    Combining_Diacritical_Marks_For_Symbols = "Diacriticals_For_Symbols"
    Combining_Diacritical_Marks_Supplement = "Diacriticals_Sup"
    Dingbats = "Dingbats"
    Dives_Akuru = "Dives_Akuru"
    Dogra = "Dogra"
    Domino_Tiles = "Domino"
    Duployan = "Duployan"
    Early_Dynastic_Cuneiform = "Early_Dynastic_Cuneiform"
    Egyptian_Hieroglyph_Format_Controls = "Egyptian_Hieroglyph_Format_Controls"
    Egyptian_Hieroglyphs = "Egyptian_Hieroglyphs"
    Elbasan = "Elbasan"
    Elymaic = "Elymaic"
    Emoticons = "Emoticons"
    Enclosed_Alphanumerics = "Enclosed_Alphanum"
    Enclosed_Alphanumeric_Supplement = "Enclosed_Alphanum_Sup"
    Enclosed_CJK_Letters_And_Months = "Enclosed_CJK"
    Enclosed_Ideographic_Supplement = "Enclosed_Ideographic_Sup"
    Ethiopic = "Ethiopic"
    Ethiopic_Extended = "Ethiopic_Ext"
    Ethiopic_Extended_A = "Ethiopic_Ext_A"
    Ethiopic_Extended_B = "Ethiopic_Ext_B"
    Ethiopic_Supplement = "Ethiopic_Sup"
    Geometric_Shapes = "Geometric_Shapes"
    Geometric_Shapes_Extended = "Geometric_Shapes_Ext"
    Georgian = "Georgian"
    Georgian_Extended = "Georgian_Ext"
    Georgian_Supplement = "Georgian_Sup"
    Glagolitic = "Glagolitic"
    Glagolitic_Supplement = "Glagolitic_Sup"
    Gothic = "Gothic"
    Grantha = "Grantha"
    Greek_And_Coptic = "Greek"
    Greek_Extended = "Greek_Ext"
    Gujarati = "Gujarati"
    Gunjala_Gondi = "Gunjala_Gondi"
    Gurmukhi = "Gurmukhi"
    Halfwidth_And_Fullwidth_Forms = "Half_And_Full_Forms"
    Combining_Half_Marks = "Half_Marks"
    Hangul_Syllables = "Hangul"
    Hanifi_Rohingya = "Hanifi_Rohingya"
    Hanunoo = "Hanunoo"
    Hatran = "Hatran"
    Hebrew = "Hebrew"
    High_Private_Use_Surrogates = "High_PU_Surrogates"
    High_Surrogates = "High_Surrogates"
    Hiragana = "Hiragana"
    Ideographic_Description_Characters = "IDC"
    Ideographic_Symbols_And_Punctuation = "Ideographic_Symbols"
    Imperial_Aramaic = "Imperial_Aramaic"
    Common_Indic_Number_Forms = "Indic_Number_Forms"
    Indic_Siyaq_Numbers = "Indic_Siyaq_Numbers"
    Inscriptional_Pahlavi = "Inscriptional_Pahlavi"
    Inscriptional_Parthian = "Inscriptional_Parthian"
    IPA_Extensions = "IPA_Ext"
    Hangul_Jamo = "Jamo"
    Hangul_Jamo_Extended_A = "Jamo_Ext_A"
    Hangul_Jamo_Extended_B = "Jamo_Ext_B"
    Javanese = "Javanese"
    Kaithi = "Kaithi"
    Kaktovik_Numerals = "Kaktovik_Numerals"
    Kana_Extended_A = "Kana_Ext_A"
    Kana_Extended_B = "Kana_Ext_B"
    Kana_Supplement = "Kana_Sup"
    Kanbun = "Kanbun"
    Kangxi_Radicals = "Kangxi"
    Kannada = "Kannada"
    Katakana = "Katakana"
    Katakana_Phonetic_Extensions = "Katakana_Ext"
    Kawi = "Kawi"
    Kayah_Li = "Kayah_Li"
    Kharoshthi = "Kharoshthi"
    Khitan_Small_Script = "Khitan_Small_Script"
    Khmer = "Khmer"
    Khmer_Symbols = "Khmer_Symbols"
    Khojki = "Khojki"
    Khudawadi = "Khudawadi"
    Lao = "Lao"
    Latin_1_Supplement = "Latin_1_Sup"
    Latin_Extended_A = "Latin_Ext_A"
    Latin_Extended_Additional = "Latin_Ext_Additional"
    Latin_Extended_B = "Latin_Ext_B"
    Latin_Extended_C = "Latin_Ext_C"
    Latin_Extended_D = "Latin_Ext_D"
    Latin_Extended_E = "Latin_Ext_E"
    Latin_Extended_F = "Latin_Ext_F"
    Latin_Extended_G = "Latin_Ext_G"
    Lepcha = "Lepcha"
    Letterlike_Symbols = "Letterlike_Symbols"
    Limbu = "Limbu"
    Linear_A = "Linear_A"
    Linear_B_Ideograms = "Linear_B_Ideograms"
    Linear_B_Syllabary = "Linear_B_Syllabary"
    Lisu = "Lisu"
    Lisu_Supplement = "Lisu_Sup"
    Low_Surrogates = "Low_Surrogates"
    Lycian = "Lycian"
    Lydian = "Lydian"
    Mahajani = "Mahajani"
    Mahjong_Tiles = "Mahjong"
    Makasar = "Makasar"
    Malayalam = "Malayalam"
    Mandaic = "Mandaic"
    Manichaean = "Manichaean"
    Marchen = "Marchen"
    Masaram_Gondi = "Masaram_Gondi"
    Mathematical_Alphanumeric_Symbols = "Math_Alphanum"
    Mathematical_Operators = "Math_Operators"
    Mayan_Numerals = "Mayan_Numerals"
    Medefaidrin = "Medefaidrin"
    Meetei_Mayek = "Meetei_Mayek"
    Meetei_Mayek_Extensions = "Meetei_Mayek_Ext"
    Mende_Kikakui = "Mende_Kikakui"
    Meroitic_Cursive = "Meroitic_Cursive"
    Meroitic_Hieroglyphs = "Meroitic_Hieroglyphs"
    Miao = "Miao"
    Miscellaneous_Symbols_And_Arrows = "Misc_Arrows"
    Miscellaneous_Mathematical_Symbols_A = "Misc_Math_Symbols_A"
    Miscellaneous_Mathematical_Symbols_B = "Misc_Math_Symbols_B"
    Miscellaneous_Symbols_And_Pictographs = "Misc_Pictographs"
    Miscellaneous_Symbols = "Misc_Symbols"
    Miscellaneous_Technical = "Misc_Technical"
    Modi = "Modi"
    Spacing_Modifier_Letters = "Modifier_Letters"
    Modifier_Tone_Letters = "Modifier_Tone_Letters"
    Mongolian = "Mongolian"
    Mongolian_Supplement = "Mongolian_Sup"
    Mro = "Mro"
    Multani = "Multani"
    Musical_Symbols = "Music"
    Myanmar = "Myanmar"
    Myanmar_Extended_A = "Myanmar_Ext_A"
    Myanmar_Extended_B = "Myanmar_Ext_B"
    Nabataean = "Nabataean"
    Nag_Mundari = "Nag_Mundari"
    Nandinagari = "Nandinagari"
    No_Block = "NB"
    New_Tai_Lue = "New_Tai_Lue"
    Newa = "Newa"
    NKo = "NKo"
    Number_Forms = "Number_Forms"
    Nushu = "Nushu"
    Nyiakeng_Puachue_Hmong = "Nyiakeng_Puachue_Hmong"
    Optical_Character_Recognition = "OCR"
    Ogham = "Ogham"
    Ol_Chiki = "Ol_Chiki"
    Old_Hungarian = "Old_Hungarian"
    Old_Italic = "Old_Italic"
    Old_North_Arabian = "Old_North_Arabian"
    Old_Permic = "Old_Permic"
    Old_Persian = "Old_Persian"
    Old_Sogdian = "Old_Sogdian"
    Old_South_Arabian = "Old_South_Arabian"
    Old_Turkic = "Old_Turkic"
    Old_Uyghur = "Old_Uyghur"
    Oriya = "Oriya"
    Ornamental_Dingbats = "Ornamental_Dingbats"
    Osage = "Osage"
    Osmanya = "Osmanya"
    Ottoman_Siyaq_Numbers = "Ottoman_Siyaq_Numbers"
    Pahawh_Hmong = "Pahawh_Hmong"
    Palmyrene = "Palmyrene"
    Pau_Cin_Hau = "Pau_Cin_Hau"
    Phags_Pa = "Phags_Pa"
    Phaistos_Disc = "Phaistos"
    Phoenician = "Phoenician"
    Phonetic_Extensions = "Phonetic_Ext"
    Phonetic_Extensions_Supplement = "Phonetic_Ext_Sup"
    Playing_Cards = "Playing_Cards"
    Psalter_Pahlavi = "Psalter_Pahlavi"
    Private_Use_Area = "PUA"
    General_Punctuation = "Punctuation"
    Rejang = "Rejang"
    Rumi_Numeral_Symbols = "Rumi"
    Runic = "Runic"
    Samaritan = "Samaritan"
    Saurashtra = "Saurashtra"
    Sharada = "Sharada"
    Shavian = "Shavian"
    Shorthand_Format_Controls = "Shorthand_Format_Controls"
    Siddham = "Siddham"
    Sinhala = "Sinhala"
    Sinhala_Archaic_Numbers = "Sinhala_Archaic_Numbers"
    Small_Form_Variants = "Small_Forms"
    Small_Kana_Extension = "Small_Kana_Ext"
    Sogdian = "Sogdian"
    Sora_Sompeng = "Sora_Sompeng"
    Soyombo = "Soyombo"
    Specials = "Specials"
    Sundanese = "Sundanese"
    Sundanese_Supplement = "Sundanese_Sup"
    Supplemental_Arrows_A = "Sup_Arrows_A"
    Supplemental_Arrows_B = "Sup_Arrows_B"
    Supplemental_Arrows_C = "Sup_Arrows_C"
    Supplemental_Mathematical_Operators = "Sup_Math_Operators"
    Supplementary_Private_Use_Area_A = "Sup_PUA_A"
    Supplementary_Private_Use_Area_B = "Sup_PUA_B"
    Supplemental_Punctuation = "Sup_Punctuation"
    Supplemental_Symbols_And_Pictographs = "Sup_Symbols_And_Pictographs"
    Superscripts_And_Subscripts = "Super_And_Sub"
    Sutton_SignWriting = "Sutton_SignWriting"
    Syloti_Nagri = "Syloti_Nagri"
    Symbols_And_Pictographs_Extended_A = "Symbols_And_Pictographs_Ext_A"
    Symbols_For_Legacy_Computing = "Symbols_For_Legacy_Computing"
    Syriac = "Syriac"
    Syriac_Supplement = "Syriac_Sup"
    Tagalog = "Tagalog"
    Tagbanwa = "Tagbanwa"
    Tags = "Tags"
    Tai_Le = "Tai_Le"
    Tai_Tham = "Tai_Tham"
    Tai_Viet = "Tai_Viet"
    Tai_Xuan_Jing_Symbols = "Tai_Xuan_Jing"
    Takri = "Takri"
    Tamil = "Tamil"
    Tamil_Supplement = "Tamil_Sup"
    Tangsa = "Tangsa"
    Tangut = "Tangut"
    Tangut_Components = "Tangut_Components"
    Tangut_Supplement = "Tangut_Sup"
    Telugu = "Telugu"
    Thaana = "Thaana"
    Thai = "Thai"
    Tibetan = "Tibetan"
    Tifinagh = "Tifinagh"
    Tirhuta = "Tirhuta"
    Toto = "Toto"
    Transport_And_Map_Symbols = "Transport_And_Map"
    Unified_Canadian_Aboriginal_Syllabics = "UCAS"
    Unified_Canadian_Aboriginal_Syllabics_Extended = "UCAS_Ext"
    Unified_Canadian_Aboriginal_Syllabics_Extended_A = "UCAS_Ext_A"
    Ugaritic = "Ugaritic"
    Vai = "Vai"
    Vedic_Extensions = "Vedic_Ext"
    Vertical_Forms = "Vertical_Forms"
    Vithkuqi = "Vithkuqi"
    Variation_Selectors = "VS"
    Variation_Selectors_Supplement = "VS_Sup"
    Wancho = "Wancho"
    Warang_Citi = "Warang_Citi"
    Yezidi = "Yezidi"
    Yi_Radicals = "Yi_Radicals"
    Yi_Syllables = "Yi_Syllables"
    Yijing_Hexagram_Symbols = "Yijing"
    Zanabazar_Square = "Zanabazar_Square"
    Znamenny_Musical_Notation = "Znamenny_Music"

BLK = Block


class Canonical_Combining_Class(Property, IntEnum):
    Not_Reordered = 0
    NR = 0
    Overlay = 1
    OV = 1
    Han_Reading = 6
    HANR = 6
    Nukta = 7
    NK = 7
    Kana_Voicing = 8
    KV = 8
    Virama = 9
    VR = 9
    CCC10 = 10
    CCC11 = 11
    CCC12 = 12
    CCC13 = 13
    CCC14 = 14
    CCC15 = 15
    CCC16 = 16
    CCC17 = 17
    CCC18 = 18
    CCC19 = 19
    CCC20 = 20
    CCC21 = 21
    CCC22 = 22
    CCC23 = 23
    CCC24 = 24
    CCC25 = 25
    CCC26 = 26
    CCC27 = 27
    CCC28 = 28
    CCC29 = 29
    CCC30 = 30
    CCC31 = 31
    CCC32 = 32
    CCC33 = 33
    CCC34 = 34
    CCC35 = 35
    CCC36 = 36
    CCC84 = 84
    CCC91 = 91
    CCC103 = 103
    CCC107 = 107
    CCC118 = 118
    CCC122 = 122
    CCC129 = 129
    CCC130 = 130
    CCC132 = 132
    CCC133 = 133
    Attached_Below_Left = 200
    ATBL = 200
    Attached_Below = 202
    ATB = 202
    Attached_Above = 214
    ATA = 214
    Attached_Above_Right = 216
    ATAR = 216
    Below_Left = 218
    BL = 218
    Below = 220
    B = 220
    Below_Right = 222
    BR = 222
    Left = 224
    L = 224
    Right = 226
    R = 226
    Above_Left = 228
    AL = 228
    Above = 230
    A = 230
    Above_Right = 232
    AR = 232
    Double_Below = 233
    DB = 233
    Double_Above = 234
    DA = 234
    Iota_Subscript = 240
    IS = 240

CCC = Canonical_Combining_Class


class Default_Ignorable_Code_Point(Property, StrEnum):
    No = "N"
    Yes = "Y"

DI = Default_Ignorable_Code_Point


class East_Asian_Width(Property, StrEnum):
    Ambiguous = "A"
    Fullwidth = "F"
    Halfwidth = "H"
    Neutral = "N"
    Narrow = "Na"
    Wide = "W"

EA = East_Asian_Width


class Emoji(Property, StrEnum):
    No = "N"
    Yes = "Y"


class Emoji_Component(Property, StrEnum):
    No = "N"
    Yes = "Y"

EComp = Emoji_Component


class Emoji_Modifier(Property, StrEnum):
    No = "N"
    Yes = "Y"

EMod = Emoji_Modifier


class Emoji_Modifier_Base(Property, StrEnum):
    No = "N"
    Yes = "Y"

EBase = Emoji_Modifier_Base


class Emoji_Presentation(Property, StrEnum):
    No = "N"
    Yes = "Y"

EPres = Emoji_Presentation


class Extended_Pictographic(Property, StrEnum):
    No = "N"
    Yes = "Y"

ExtPict = Extended_Pictographic


class General_Category(Property, StrEnum):
    Other = "C"
    Control = "Cc"
    Format = "Cf"
    Unassigned = "Cn"
    Private_Use = "Co"
    Surrogate = "Cs"
    Letter = "L"
    Cased_Letter = "LC"
    Lowercase_Letter = "Ll"
    Modifier_Letter = "Lm"
    Other_Letter = "Lo"
    Titlecase_Letter = "Lt"
    Uppercase_Letter = "Lu"
    Mark = "M"
    Spacing_Mark = "Mc"
    Enclosing_Mark = "Me"
    Nonspacing_Mark = "Mn"
    Number = "N"
    Decimal_Number = "Nd"
    Letter_Number = "Nl"
    Other_Number = "No"
    Punctuation = "P"
    Connector_Punctuation = "Pc"
    Dash_Punctuation = "Pd"
    Close_Punctuation = "Pe"
    Final_Punctuation = "Pf"
    Initial_Punctuation = "Pi"
    Other_Punctuation = "Po"
    Open_Punctuation = "Ps"
    Symbol = "S"
    Currency_Symbol = "Sc"
    Modifier_Symbol = "Sk"
    Math_Symbol = "Sm"
    Other_Symbol = "So"
    Separator = "Z"
    Line_Separator = "Zl"
    Paragraph_Separator = "Zp"
    Space_Separator = "Zs"

GC = General_Category


class Indic_Conjunct_Break(Property, StrEnum):
    Consonant = "Consonant"
    Extend = "Extend"
    Linker = "Linker"
    None_ = "None"

InCB = Indic_Conjunct_Break


class Indic_Syllabic_Category(Property, StrEnum):
    Avagraha = "Avagraha"
    Bindu = "Bindu"
    Brahmi_Joining_Number = "Brahmi_Joining_Number"
    Cantillation_Mark = "Cantillation_Mark"
    Consonant = "Consonant"
    Consonant_Dead = "Consonant_Dead"
    Consonant_Final = "Consonant_Final"
    Consonant_Head_Letter = "Consonant_Head_Letter"
    Consonant_Initial_Postfixed = "Consonant_Initial_Postfixed"
    Consonant_Killer = "Consonant_Killer"
    Consonant_Medial = "Consonant_Medial"
    Consonant_Placeholder = "Consonant_Placeholder"
    Consonant_Preceding_Repha = "Consonant_Preceding_Repha"
    Consonant_Prefixed = "Consonant_Prefixed"
    Consonant_Repha = "Consonant_Repha"
    Consonant_Subjoined = "Consonant_Subjoined"
    Consonant_Succeeding_Repha = "Consonant_Succeeding_Repha"
    Consonant_With_Stacker = "Consonant_With_Stacker"
    Gemination_Mark = "Gemination_Mark"
    Invisible_Stacker = "Invisible_Stacker"
    Joiner = "Joiner"
    Modifying_Letter = "Modifying_Letter"
    Non_Joiner = "Non_Joiner"
    Nukta = "Nukta"
    Number = "Number"
    Number_Joiner = "Number_Joiner"
    Other = "Other"
    Pure_Killer = "Pure_Killer"
    Register_Shifter = "Register_Shifter"
    Syllable_Modifier = "Syllable_Modifier"
    Tone_Letter = "Tone_Letter"
    Tone_Mark = "Tone_Mark"
    Virama = "Virama"
    Visarga = "Visarga"
    Vowel = "Vowel"
    Vowel_Dependent = "Vowel_Dependent"
    Vowel_Independent = "Vowel_Independent"

InSC = Indic_Syllabic_Category


class Script(Property, StrEnum):
    Adlam = "Adlm"
    Caucasian_Albanian = "Aghb"
    Ahom = "Ahom"
    Arabic = "Arab"
    Imperial_Aramaic = "Armi"
    Armenian = "Armn"
    Avestan = "Avst"
    Balinese = "Bali"
    Bamum = "Bamu"
    Bassa_Vah = "Bass"
    Batak = "Batk"
    Bengali = "Beng"
    Bhaiksuki = "Bhks"
    Bopomofo = "Bopo"
    Brahmi = "Brah"
    Braille = "Brai"
    Buginese = "Bugi"
    Buhid = "Buhd"
    Chakma = "Cakm"
    Canadian_Aboriginal = "Cans"
    Carian = "Cari"
    Cham = "Cham"
    Cherokee = "Cher"
    Chorasmian = "Chrs"
    Coptic = "Copt"
    Cypro_Minoan = "Cpmn"
    Cypriot = "Cprt"
    Cyrillic = "Cyrl"
    Devanagari = "Deva"
    Dives_Akuru = "Diak"
    Dogra = "Dogr"
    Deseret = "Dsrt"
    Duployan = "Dupl"
    Egyptian_Hieroglyphs = "Egyp"
    Elbasan = "Elba"
    Elymaic = "Elym"
    Ethiopic = "Ethi"
    Georgian = "Geor"
    Glagolitic = "Glag"
    Gunjala_Gondi = "Gong"
    Masaram_Gondi = "Gonm"
    Gothic = "Goth"
    Grantha = "Gran"
    Greek = "Grek"
    Gujarati = "Gujr"
    Gurmukhi = "Guru"
    Hangul = "Hang"
    Han = "Hani"
    Hanunoo = "Hano"
    Hatran = "Hatr"
    Hebrew = "Hebr"
    Hiragana = "Hira"
    Anatolian_Hieroglyphs = "Hluw"
    Pahawh_Hmong = "Hmng"
    Nyiakeng_Puachue_Hmong = "Hmnp"
    Katakana_Or_Hiragana = "Hrkt"
    Old_Hungarian = "Hung"
    Old_Italic = "Ital"
    Javanese = "Java"
    Kayah_Li = "Kali"
    Katakana = "Kana"
    Kawi = "Kawi"
    Kharoshthi = "Khar"
    Khmer = "Khmr"
    Khojki = "Khoj"
    Khitan_Small_Script = "Kits"
    Kannada = "Knda"
    Kaithi = "Kthi"
    Tai_Tham = "Lana"
    Lao = "Laoo"
    Latin = "Latn"
    Lepcha = "Lepc"
    Limbu = "Limb"
    Linear_A = "Lina"
    Linear_B = "Linb"
    Lisu = "Lisu"
    Lycian = "Lyci"
    Lydian = "Lydi"
    Mahajani = "Mahj"
    Makasar = "Maka"
    Mandaic = "Mand"
    Manichaean = "Mani"
    Marchen = "Marc"
    Medefaidrin = "Medf"
    Mende_Kikakui = "Mend"
    Meroitic_Cursive = "Merc"
    Meroitic_Hieroglyphs = "Mero"
    Malayalam = "Mlym"
    Modi = "Modi"
    Mongolian = "Mong"
    Mro = "Mroo"
    Meetei_Mayek = "Mtei"
    Multani = "Mult"
    Myanmar = "Mymr"
    Nag_Mundari = "Nagm"
    Nandinagari = "Nand"
    Old_North_Arabian = "Narb"
    Nabataean = "Nbat"
    Newa = "Newa"
    Nko = "Nkoo"
    Nushu = "Nshu"
    Ogham = "Ogam"
    Ol_Chiki = "Olck"
    Old_Turkic = "Orkh"
    Oriya = "Orya"
    Osage = "Osge"
    Osmanya = "Osma"
    Old_Uyghur = "Ougr"
    Palmyrene = "Palm"
    Pau_Cin_Hau = "Pauc"
    Old_Permic = "Perm"
    Phags_Pa = "Phag"
    Inscriptional_Pahlavi = "Phli"
    Psalter_Pahlavi = "Phlp"
    Phoenician = "Phnx"
    Miao = "Plrd"
    Inscriptional_Parthian = "Prti"
    Rejang = "Rjng"
    Hanifi_Rohingya = "Rohg"
    Runic = "Runr"
    Samaritan = "Samr"
    Old_South_Arabian = "Sarb"
    Saurashtra = "Saur"
    SignWriting = "Sgnw"
    Shavian = "Shaw"
    Sharada = "Shrd"
    Siddham = "Sidd"
    Khudawadi = "Sind"
    Sinhala = "Sinh"
    Sogdian = "Sogd"
    Old_Sogdian = "Sogo"
    Sora_Sompeng = "Sora"
    Soyombo = "Soyo"
    Sundanese = "Sund"
    Syloti_Nagri = "Sylo"
    Syriac = "Syrc"
    Tagbanwa = "Tagb"
    Takri = "Takr"
    Tai_Le = "Tale"
    New_Tai_Lue = "Talu"
    Tamil = "Taml"
    Tangut = "Tang"
    Tai_Viet = "Tavt"
    Telugu = "Telu"
    Tifinagh = "Tfng"
    Tagalog = "Tglg"
    Thaana = "Thaa"
    Thai = "Thai"
    Tibetan = "Tibt"
    Tirhuta = "Tirh"
    Tangsa = "Tnsa"
    Toto = "Toto"
    Ugaritic = "Ugar"
    Vai = "Vaii"
    Vithkuqi = "Vith"
    Warang_Citi = "Wara"
    Wancho = "Wcho"
    Old_Persian = "Xpeo"
    Cuneiform = "Xsux"
    Yezidi = "Yezi"
    Yi = "Yiii"
    Zanabazar_Square = "Zanb"
    Inherited = "Zinh"
    Common = "Zyyy"
    Unknown = "Zzzz"

SC = Script


class White_Space(Property, StrEnum):
    No = "N"
    Yes = "Y"

WSpace = White_Space
