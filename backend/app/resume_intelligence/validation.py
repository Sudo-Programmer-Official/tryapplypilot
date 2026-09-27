from __future__ import annotations

import math

from .models import ResumeChangeReviewInput, ResumeIntelligenceAnalysis


def estimate_resume_pages(text: str, *, max_chars_per_line: int = 92, lines_per_page: int = 44) -> int:
    non_empty_lines = [line.rstrip() for line in text.splitlines()]
    line_count = 0
    for line in non_empty_lines:
        if not line.strip():
            line_count += 1
            continue
        line_count += max(1, math.ceil(len(line) / max_chars_per_line))
    return max(1, math.ceil(line_count / max(lines_per_page, 1)))


def validate_final_resume_text(
    *,
    analysis: ResumeIntelligenceAnalysis,
    final_text: str,
    accepted_reviews: list[ResumeChangeReviewInput],
) -> list[str]:
    errors: list[str] = []
    normalized_text = "\n".join(line.rstrip() for line in final_text.splitlines()).strip()
    if not normalized_text:
        errors.append("Final resume text cannot be empty.")
        return errors

    blocked_labels = {label.casefold() for label in analysis.change_set.blocked_requirements}
    for review in accepted_reviews:
        edited_text = review.edited_text.casefold().strip()
        if blocked_labels and any(label in edited_text for label in blocked_labels):
            errors.append("Approved changes cannot introduce blocked requirements.")
            break

    seen_lines: set[str] = set()
    for raw_line in normalized_text.splitlines():
        line = " ".join(raw_line.split()).strip().casefold()
        if not line:
            continue
        if line in seen_lines:
            errors.append("Final resume contains duplicated lines.")
            break
        seen_lines.add(line)

    if estimate_resume_pages(normalized_text) > 2:
        errors.append("Final resume exceeds the two-page limit for V1 PDF generation.")

    if "experience" not in normalized_text.casefold() and "project" not in normalized_text.casefold():
        errors.append("Final resume must retain at least one experience or project section.")

    return errors
