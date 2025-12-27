"""
STT Patterns Configuration

Speech-to-Text correction patterns for voice input normalization.
"""

# Email patterns
STT_EMAIL_PATTERNS = {
    'at the rate': '@',
    'at the rate of': '@',
    'at sign': '@',
    'at symbol': '@',
    'dot com': '.com',
    'dot org': '.org',
    'dot net': '.net',
    'dot edu': '.edu',
    'dot co': '.co',
    'dot gov': '.gov',
    'dot io': '.io',
    'dotcom': '.com',
    'gmail dot com': 'gmail.com',
    'yahoo dot com': 'yahoo.com',
    'hotmail dot com': 'hotmail.com',
    'outlook dot com': 'outlook.com',
}

# Punctuation patterns
STT_PUNCTUATION = {
    'underscore': '_',
    'under score': '_',
    'hyphen': '-',
    'minus': '-',
    'dash': '-',
    'en dash': '-',
    'period': '.',
    'dot': '.',
    'full stop': '.',
    'space': ' ',
    'plus': '+',
    'plus sign': '+',
    'hash': '#',
    'hashtag': '#',
    'pound': '#',
    'star': '*',
    'asterisk': '*',
    'ampersand': '&',
    'and sign': '&',
    'forward slash': '/',
    'slash': '/',
    'backslash': '\\',
    'colon': ':',
    'semicolon': ';',
    'comma': ',',
}

# Number word mappings
NUMBER_WORDS = {
    'zero': '0', 'oh': '0', 'o': '0',
    'one': '1', 'won': '1',
    'two': '2', 'to': '2', 'too': '2',
    'three': '3', 'tree': '3',
    'four': '4', 'for': '4',
    'five': '5', 'fife': '5',
    'six': '6',
    'seven': '7',
    'eight': '8', 'ate': '8',
    'nine': '9', 'niner': '9',
    'ten': '10',
    'eleven': '11',
    'twelve': '12',
    'thirteen': '13',
    'fourteen': '14',
    'fifteen': '15',
    'sixteen': '16',
    'seventeen': '17',
    'eighteen': '18',
    'nineteen': '19',
    'twenty': '20',
    'thirty': '30',
    'forty': '40',
    'fifty': '50',
    'sixty': '60',
    'seventy': '70',
    'eighty': '80',
    'ninety': '90',
    'hundred': '00',
    'thousand': '000',
    # Ordinals
    'first': '1', 'second': '2', 'third': '3', 'fourth': '4', 'fifth': '5',
    'sixth': '6', 'seventh': '7', 'eighth': '8', 'ninth': '9', 'tenth': '10',
    'eleventh': '11', 'twelfth': '12', 'thirteenth': '13', 'fourteenth': '14',
    'fifteenth': '15', 'sixteenth': '16', 'seventeenth': '17', 'eighteenth': '18',
    'nineteenth': '19', 'twentieth': '20',
    'thirtieth': '30',
}

# Compound number words
COMPOUND_NUMBERS = {
    'twenty one': '21', 'twenty two': '22', 'twenty three': '23',
    'twenty four': '24', 'twenty five': '25', 'twenty six': '26',
    'twenty seven': '27', 'twenty eight': '28', 'twenty nine': '29',
    'thirty one': '31', 'thirty two': '32', 'thirty three': '33',
}

# Common homophones that cause STT confusion
HOMOPHONES = {
    'male': 'mail',
    'their': 'there',
    'your': "you're",
    'hear': 'here',
    'write': 'right',
    'weight': 'wait',
}


def get_all_stt_patterns():
    """Get all STT patterns combined."""
    patterns = {}
    patterns.update(STT_EMAIL_PATTERNS)
    patterns.update(STT_PUNCTUATION)
    return patterns
