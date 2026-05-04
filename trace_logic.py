import re


def build_identifier_pattern(prefix, digits):
    return re.compile(rf"^{re.escape(prefix)}(\d{{{digits}}})$")


def analyze_identifier_series(series, prefix, digits):
    pattern = build_identifier_pattern(prefix, digits)
    total_values = 0
    match_count = 0
    numbers = set()

    for value in series.dropna():
        text = str(value).strip().upper()
        if not text:
            continue

        total_values += 1
        match = pattern.match(text)
        if match:
            match_count += 1
            numbers.add(int(match.group(1)))

    return {
        "total_values": total_values,
        "match_count": match_count,
        "numbers": sorted(numbers),
    }


def extract_numbers(series, prefix, digits):
    analysis = analyze_identifier_series(series, prefix, digits)
    return analysis["numbers"]


def has_identifier_values(series, prefix, digits, minimum_match_ratio=0.5):
    analysis = analyze_identifier_series(series, prefix, digits)
    total_values = analysis["total_values"]

    if total_values == 0 or analysis["match_count"] == 0:
        return False

    return (analysis["match_count"] / total_values) >= minimum_match_ratio


def find_missing_ids(numbers, start_number, max_range, prefix, digits):
    existing = set(numbers)
    return [
        f"{prefix}{number:0{digits}d}"
        for number in range(start_number, max_range + 1)
        if number not in existing
    ]
