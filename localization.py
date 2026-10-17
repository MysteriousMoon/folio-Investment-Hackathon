"""Normalize legacy profile enum identifiers without rewriting conversation history."""

# Unicode escapes preserve compatibility with profiles saved before English localization.
LEGACY_PROFILE_VALUES = {
    "risk": {
        "\u7a33\u5065": "conservative",
        "\u5747\u8861": "balanced",
        "\u79ef\u6781": "aggressive",
    },
    "currency": {
        "\u4eba\u6c11\u5e01": "CNY",
        "\u7f8e\u5143": "USD",
        "\u52a0\u5143": "CAD",
    },
    "market": {
        "\u7f8e\u80a1": "US stocks",
        "A\u80a1": "A shares",
        "A \u80a1": "A shares",
        "\u6e2f\u80a1": "Hong Kong stocks",
    },
}


def normalize_profile(profile):
    """Return a copy with equivalent English enum values; retain all other fields."""
    result = dict(profile)
    for field, aliases in LEGACY_PROFILE_VALUES.items():
        value = result.get(field)
        if isinstance(value, str) and value in aliases:
            result[field] = aliases[value]
    return result
