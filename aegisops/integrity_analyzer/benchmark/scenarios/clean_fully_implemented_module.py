"""Compute summary statistics for a list of numbers."""


def compute_average(numbers: list[float]) -> float:
    return sum(numbers) / len(numbers)


def compute_max(numbers: list[float]) -> float:
    return max(numbers)
