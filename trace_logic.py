import re


def extract_numbers(series):
    numbers = set()

    for val in series.dropna():
        match = re.search(r"(\d+)", str(val))
        if match:
            numbers.add(int(match.group(1)))

    return sorted(numbers)


def find_missing(numbers, max_range):
    existing = set(numbers)
    return [
        f"TMGID{i:06d}"
        for i in range(1, max_range + 1)
        if i not in existing
    ]
