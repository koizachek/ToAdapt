"""Case-Manager — JSON-basierter Pool mit Approval-Workflow."""

import json
import os
from pathlib import Path

import structlog

from backend.models.case import Case, CaseStatus, CaseSummary

logger = structlog.get_logger(__name__)

POOL_DIR = Path(__file__).parent / "pool"
POOL_DIR.mkdir(exist_ok=True)


class CaseManager:
    """Verwaltet den kuratierten Case-Pool als JSON-Dateien."""

    def _path(self, case_id: str) -> Path:
        return POOL_DIR / f"{case_id}.json"

    def save(self, case: Case) -> None:
        self._path(case.case_id).write_text(
            case.model_dump_json(indent=2), encoding="utf-8"
        )
        logger.info("case_saved", case_id=case.case_id, status=case.status)

    def get(self, case_id: str) -> Case | None:
        p = self._path(case_id)
        if not p.exists():
            return None
        return Case.model_validate_json(p.read_text(encoding="utf-8"))

    def list_all(
        self,
        status: str | None = None,
        language: str | None = None,
    ) -> list[CaseSummary]:
        cases = []
        for f in POOL_DIR.glob("*.json"):
            if f.name.endswith("-agent.json"):
                continue
            try:
                c = Case.model_validate_json(f.read_text(encoding="utf-8"))
                status_matches = status is None or c.status == status
                language_matches = language is None or c.language == language
                if status_matches and language_matches:
                    cases.append(CaseSummary(
                        case_id=c.case_id,
                        title=c.title,
                        industry=c.industry,
                        difficulty=c.difficulty,
                        status=c.status,
                        created_at=c.created_at,
                        language=c.language,
                        translated_from=c.translated_from,
                    ))
            except Exception as e:
                logger.warning("case_load_error", file=str(f), error=str(e))
        return sorted(cases, key=lambda x: x.created_at, reverse=True)

    def approve(self, case_id: str, reviewer: str, notes: str = "") -> Case | None:
        case = self.get(case_id)
        if not case:
            return None
        case.status = CaseStatus.APPROVED
        case.reviewed_by = reviewer
        case.review_notes = notes
        from datetime import datetime
        case.approved_at = datetime.utcnow()
        self.save(case)
        return case

    def reject(self, case_id: str, reviewer: str, notes: str = "") -> Case | None:
        case = self.get(case_id)
        if not case:
            return None
        case.status = CaseStatus.REJECTED
        case.reviewed_by = reviewer
        case.review_notes = notes
        self.save(case)
        return case

    def approved_pool(self, target_tp: int | None = None) -> list[Case]:
        """Gibt alle approvedCases zurück, optional gefiltert nach TP."""
        result = []
        for summary in self.list_all(status=CaseStatus.APPROVED):
            case = self.get(summary.case_id)
            if case and (target_tp is None or case.target_tp == target_tp):
                result.append(case)
        return result


case_manager = CaseManager()
