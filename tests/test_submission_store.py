from backend.api import routes
from backend.models.submission import Submission, SubmissionStatus


async def test_get_submission_recovers_from_store(monkeypatch):
    submission = Submission(
        submission_id="sub-123",
        user_id="user-1",
        matrikelnummer="pid-1",
        case_id="alpes-bank-genai-001",
        target_tp=1,
        status=SubmissionStatus.IN_PROGRESS,
    )

    routes._submissions.clear()
    monkeypatch.setattr(routes.submission_store, "load", lambda submission_id: submission if submission_id == "sub-123" else None)

    recovered = await routes._get_submission("sub-123")

    assert recovered is not None
    assert recovered.submission_id == "sub-123"
    assert routes._submissions["sub-123"].submission_id == "sub-123"
