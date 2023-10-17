import unittest

from demicode.metamodel import are_same_name

class TestMetaModel(unittest.TestCase):

    def test_are_same_name(self) -> None:
        for name1, name2, match in (
            ('isEmoji', 'Emoji', True),
            ('is Emoji Modifier', 'Emoji_Modifier', True),
            ('is_emoji_modifier', 'Emoji_Modifier', True),
            ('is-emoji-modifier', 'Emoji_Modifier', True),
            ('d-a-s-h', 'Dash', True),
            ('d a s h', 'Dash', True),
            ('d_a_s_h', 'Dash', True),
            ('isDash', 'Dash', True),
        ):
            if match:
                self.assertTrue(are_same_name(name1, name2))
            else:
                self.assertFalse(are_same_name(name1, name2))
