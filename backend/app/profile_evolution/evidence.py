from __future__ import annotations

from .conversation import ProfileEvolutionQuestion, ProfileEvolutionSession


def build_conversation_evidence_metadata(
    *,
    session: ProfileEvolutionSession,
    question: ProfileEvolutionQuestion | None,
    answer: str,
    topic: str,
    confidence: float,
) -> dict[str, object]:
    return {
        "source": "profile_evolution",
        "session_id": session.id,
        "topic": topic,
        "question_id": question.id if question is not None else "",
        "question_prompt": question.prompt if question is not None else "",
        "answer_preview": " ".join(answer.split())[:240],
        "confidence": confidence,
    }
