from backend.app.application.research import ResearchOutcome


class InMemoryResearchRepository:
    def __init__(self) -> None:
        self.outcomes: list[ResearchOutcome] = []

    async def save(self, outcome: ResearchOutcome) -> None:
        self.outcomes.append(outcome)
