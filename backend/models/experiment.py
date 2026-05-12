"""Experiment-Kontext für Prolific- und Forschungs-Runs."""

from pydantic import BaseModel, Field


class ExperimentContext(BaseModel):
    provider: str | None = None
    experiment_name: str | None = None
    run_id: str | None = None
    condition: str | None = None
    prolific_pid: str | None = None
    prolific_study_id: str | None = None
    prolific_session_id: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)

    def normalized(self) -> "ExperimentContext":
        provider = self.provider
        if not provider and (
            self.prolific_pid or self.prolific_study_id or self.prolific_session_id
        ):
            provider = "prolific"

        run_id = self.run_id or self.prolific_session_id or self.prolific_pid

        return self.model_copy(update={"provider": provider, "run_id": run_id})
