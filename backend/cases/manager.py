"""Case-Manager — Pool mit Approval-Workflow.

Persistenz: Bei konfiguriertem MongoDB ist Mongo die primäre Quelle (nur so
überleben generierte Cases ein Redeploy auf Railway); die JSON-Dateien in
pool/ bleiben als Fallback und für die kuratierten, mit dem Image
ausgelieferten Cases. list_all() führt beide Quellen zusammen (Mongo
gewinnt bei gleicher case_id).
"""

import json

from pathlib import Path

import structlog

from backend.db import mongo
from backend.models.case import Case, CaseEditEvent, CaseStatus, CaseSummary
from backend.timeutils import naive_utcnow

logger = structlog.get_logger(__name__)

POOL_DIR = Path(__file__).parent / "pool"
POOL_DIR.mkdir(exist_ok=True)

CASES_COLLECTION = "cases"


class CaseManager:
    """Verwaltet den kuratierten Case-Pool (Mongo primär, Dateien als Fallback)."""

    def _path(self, case_id: str) -> Path:
        return POOL_DIR / f"{case_id}.json"

    def _collection(self):
        return mongo.get_collection(CASES_COLLECTION)

    def save(self, case: Case) -> None:
        case.updated_at = naive_utcnow()

        try:
            self._path(case.case_id).write_text(
                case.model_dump_json(indent=2), encoding="utf-8"
            )
        except Exception as exc:  # pragma: no cover - z.B. read-only FS
            logger.warning("case_file_save_failed", case_id=case.case_id, error=str(exc))

        collection = self._collection()
        if collection is not None:
            try:
                collection.replace_one(
                    {"case_id": case.case_id},
                    json.loads(case.model_dump_json()),
                    upsert=True,
                )
            except Exception as exc:  # pragma: no cover - external service failure
                logger.warning("case_mongo_save_failed", case_id=case.case_id, error=str(exc))

        logger.info("case_saved", case_id=case.case_id, status=case.status, revision=case.revision)

    def get(self, case_id: str) -> Case | None:
        collection = self._collection()
        if collection is not None:
            try:
                doc = collection.find_one({"case_id": case_id}, {"_id": 0})
                if doc:
                    return Case.model_validate(doc)
            except Exception as exc:  # pragma: no cover - external service failure
                logger.warning("case_mongo_load_failed", case_id=case_id, error=str(exc))

        p = self._path(case_id)
        if not p.exists():
            return None
        return Case.model_validate_json(p.read_text(encoding="utf-8"))

    def _load_all_cases(self) -> list[Case]:
        by_id: dict[str, Case] = {}

        for f in POOL_DIR.glob("*.json"):
            if f.name.endswith("-agent.json"):
                continue
            try:
                c = Case.model_validate_json(f.read_text(encoding="utf-8"))
                by_id[c.case_id] = c
            except Exception as e:
                logger.warning("case_load_error", file=str(f), error=str(e))

        collection = self._collection()
        if collection is not None:
            try:
                for doc in collection.find({}, {"_id": 0}):
                    try:
                        c = Case.model_validate(doc)
                        by_id[c.case_id] = c  # Mongo gewinnt
                    except Exception as e:
                        logger.warning("case_mongo_doc_invalid", error=str(e))
            except Exception as exc:  # pragma: no cover - external service failure
                logger.warning("case_mongo_list_failed", error=str(exc))

        return list(by_id.values())

    def list_all(
        self,
        status: str | None = None,
        language: str | None = None,
    ) -> list[CaseSummary]:
        cases = []
        for c in self._load_all_cases():
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
        return sorted(cases, key=lambda x: x.created_at, reverse=True)

    def _record(self, case: Case, editor: str, action: str, detail: str = "") -> None:
        case.edit_history.append(CaseEditEvent(editor=editor, action=action, detail=detail))

    def approve(self, case_id: str, reviewer: str, notes: str = "") -> Case | None:
        case = self.get(case_id)
        if not case:
            return None
        case.status = CaseStatus.APPROVED
        case.reviewed_by = reviewer
        case.review_notes = notes
        case.approved_at = naive_utcnow()
        self._record(case, editor=reviewer, action="approved", detail=notes)
        self.save(case)
        return case

    def reject(self, case_id: str, reviewer: str, notes: str = "") -> Case | None:
        case = self.get(case_id)
        if not case:
            return None
        case.status = CaseStatus.REJECTED
        case.reviewed_by = reviewer
        case.review_notes = notes
        self._record(case, editor=reviewer, action="rejected", detail=notes)
        self.save(case)
        return case

    def retire(self, case_id: str, reviewer: str, notes: str = "") -> Case | None:
        """Nimmt einen freigegebenen Case aus dem Studierenden-Pool."""
        case = self.get(case_id)
        if not case:
            return None
        case.status = CaseStatus.RETIRED
        case.reviewed_by = reviewer
        case.review_notes = notes
        self._record(case, editor=reviewer, action="retired", detail=notes)
        self.save(case)
        return case

    def approved_pool(self, target_tp: int | None = None) -> list[Case]:
        """Gibt alle approvedCases zurück, optional gefiltert nach TP."""
        result = []
        for c in self._load_all_cases():
            if c.status == CaseStatus.APPROVED and (target_tp is None or c.target_tp == target_tp):
                result.append(c)
        return result


case_manager = CaseManager()
