import math


class EffortEstimator:
    """Deterministic task decomposition that preserves the graph effort total."""

    DISTRIBUTION = (
        ("learn", 0.30),
        ("practice", 0.35),
        ("apply", 0.25),
        ("review", 0.10),
    )

    def task_efforts(self, total_minutes: int) -> list[tuple[str, int]]:
        total = max(60, total_minutes)
        efforts: list[tuple[str, int]] = []
        allocated = 0
        for index, (task_type, ratio) in enumerate(self.DISTRIBUTION):
            if index == len(self.DISTRIBUTION) - 1:
                minutes = total - allocated
            else:
                minutes = max(15, int(math.ceil(total * ratio / 5) * 5))
                allocated += minutes
            efforts.append((task_type, max(15, minutes)))
        drift = sum(minutes for _, minutes in efforts) - total
        if drift > 0:
            task_type, minutes = efforts[-1]
            efforts[-1] = (task_type, max(15, minutes - drift))
        return efforts
