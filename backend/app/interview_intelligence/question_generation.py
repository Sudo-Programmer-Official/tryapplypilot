from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol
from uuid import NAMESPACE_URL, uuid5

from .models import InterviewPreparationEvidenceReference, InterviewQuestionFollowUp

QUESTION_SET_STATUSES = {"draft", "active", "superseded", "archived"}
QUESTION_CATEGORIES = {
    "recruiter_screen",
    "behavioral",
    "technical",
    "coding",
    "system_design",
    "architecture",
    "leadership",
    "product_judgment",
    "domain_specific",
    "company_specific",
    "resume_deep_dive",
    "project_deep_dive",
    "career_motivation",
    "candidate_questions",
}
QUESTION_DIFFICULTIES = {"introductory", "intermediate", "advanced", "expert"}
QUESTION_PRIORITIES = {"must_prepare", "high", "medium", "low"}
QUESTION_PREPARATION_STATUSES = {"not_started", "reviewing", "prepared", "needs_practice"}
QUESTION_SET_LIMITS = {
    "minimum": 8,
    "default": 15,
    "maximum": 30,
    "max_follow_ups": 5,
}
QUESTION_STRATEGY_VERSION = "interview_questions_v1"
QUESTION_PROVIDER = "deterministic"

_CATEGORY_ORDER: dict[str, tuple[str, ...]] = {
    "recruiter_screen": ("career_motivation", "recruiter_screen", "resume_deep_dive", "company_specific", "candidate_questions"),
    "hiring_manager": ("behavioral", "resume_deep_dive", "project_deep_dive", "company_specific", "candidate_questions"),
    "technical": ("technical", "resume_deep_dive", "project_deep_dive", "behavioral", "candidate_questions"),
    "coding": ("coding", "technical", "resume_deep_dive", "behavioral", "candidate_questions"),
    "system_design": ("system_design", "architecture", "resume_deep_dive", "project_deep_dive", "candidate_questions"),
    "behavioral": ("behavioral", "leadership", "career_motivation", "resume_deep_dive", "candidate_questions"),
    "panel": ("behavioral", "technical", "project_deep_dive", "leadership", "candidate_questions"),
    "executive": ("leadership", "career_motivation", "company_specific", "behavioral", "candidate_questions"),
    "onsite": ("technical", "system_design", "behavioral", "project_deep_dive", "candidate_questions"),
    "final": ("behavioral", "leadership", "resume_deep_dive", "company_specific", "candidate_questions"),
}

_CATEGORY_COUNTS: dict[str, dict[str, int]] = {
    "recruiter_screen": {"career_motivation": 2, "recruiter_screen": 2, "resume_deep_dive": 2, "company_specific": 1, "candidate_questions": 2},
    "hiring_manager": {"behavioral": 2, "resume_deep_dive": 2, "project_deep_dive": 2, "company_specific": 1, "candidate_questions": 2},
    "technical": {"technical": 3, "resume_deep_dive": 2, "project_deep_dive": 2, "behavioral": 1, "candidate_questions": 2},
    "coding": {"coding": 3, "technical": 2, "resume_deep_dive": 2, "behavioral": 1, "candidate_questions": 2},
    "system_design": {"system_design": 3, "architecture": 2, "resume_deep_dive": 1, "project_deep_dive": 2, "candidate_questions": 2},
    "behavioral": {"behavioral": 3, "leadership": 2, "career_motivation": 1, "resume_deep_dive": 1, "candidate_questions": 2},
    "panel": {"behavioral": 2, "technical": 2, "project_deep_dive": 2, "leadership": 1, "candidate_questions": 2},
    "executive": {"leadership": 2, "career_motivation": 2, "company_specific": 1, "behavioral": 2, "candidate_questions": 2},
    "onsite": {"technical": 2, "system_design": 2, "behavioral": 2, "project_deep_dive": 2, "candidate_questions": 2},
    "final": {"behavioral": 2, "leadership": 2, "resume_deep_dive": 2, "company_specific": 1, "candidate_questions": 2},
}

_EVALUATION_DIMENSIONS: dict[str, tuple[str, ...]] = {
    "recruiter_screen": ("clarity", "career alignment", "role fit"),
    "behavioral": ("ownership", "communication", "reflection"),
    "technical": ("technical depth", "tradeoff reasoning", "production judgment"),
    "coding": ("problem solving", "correctness", "communication"),
    "system_design": ("system thinking", "scalability", "tradeoff reasoning"),
    "architecture": ("architecture judgment", "constraints", "operational awareness"),
    "leadership": ("influence", "ownership", "judgment"),
    "product_judgment": ("customer thinking", "prioritization", "decision quality"),
    "domain_specific": ("domain fluency", "problem framing", "adaptability"),
    "company_specific": ("company understanding", "motivation", "role fit"),
    "resume_deep_dive": ("accuracy", "depth", "impact"),
    "project_deep_dive": ("execution detail", "technical depth", "results"),
    "career_motivation": ("motivation", "self-awareness", "alignment"),
    "candidate_questions": ("curiosity", "judgment", "process awareness"),
}


@dataclass(frozen=True)
class QuestionPlanItem:
    category: str
    count: int
    difficulty: str
    priority: str


@dataclass(frozen=True)
class QuestionCoveragePlan:
    items: list[QuestionPlanItem] = field(default_factory=list)

    @property
    def required_categories(self) -> set[str]:
        return {item.category for item in self.items if item.count > 0}


@dataclass(frozen=True)
class QuestionExample:
    label: str
    detail: str
    evidence: list[InterviewPreparationEvidenceReference] = field(default_factory=list)
    risk_tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ResumeClaim:
    label: str
    detail: str
    requirements: list[str] = field(default_factory=list)
    evidence: list[InterviewPreparationEvidenceReference] = field(default_factory=list)
    risk_tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class QuestionGenerationContext:
    question_set_id: str
    interview_id: str
    application_id: str
    user_id: str
    interview_type: str
    interview_round: str
    company: str
    role_title: str
    focus_requirements: list[str] = field(default_factory=list)
    company_context: list[str] = field(default_factory=list)
    recruiter_context: list[str] = field(default_factory=list)
    candidate_question_prompts: list[str] = field(default_factory=list)
    job_requirement_evidence: dict[str, list[InterviewPreparationEvidenceReference]] = field(default_factory=dict)
    resume_claims: list[ResumeClaim] = field(default_factory=list)
    project_examples: list[QuestionExample] = field(default_factory=list)
    leadership_examples: list[QuestionExample] = field(default_factory=list)
    architecture_examples: list[QuestionExample] = field(default_factory=list)
    risk_examples: list[QuestionExample] = field(default_factory=list)
    application_artifacts: list[str] = field(default_factory=list)
    application_answers: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class GeneratedInterviewQuestion:
    category: str
    question: str
    rationale: str
    evaluation_dimensions: list[str] = field(default_factory=list)
    related_job_requirements: list[str] = field(default_factory=list)
    related_evidence: list[InterviewPreparationEvidenceReference] = field(default_factory=list)
    follow_up_questions: list[InterviewQuestionFollowUp] = field(default_factory=list)
    difficulty: str = "intermediate"
    priority: str = "medium"
    confidence: float = 0.0
    expected_answer_outline: list[str] = field(default_factory=list)
    risk_tags: list[str] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)


class InterviewQuestionGenerator(Protocol):
    async def generate(
        self,
        context: QuestionGenerationContext,
        coverage_plan: QuestionCoveragePlan,
    ) -> list[GeneratedInterviewQuestion]:
        ...


def build_question_coverage_plan(interview_type: str) -> QuestionCoveragePlan:
    normalized = interview_type.strip().casefold() or "technical"
    order = _CATEGORY_ORDER.get(normalized, _CATEGORY_ORDER["technical"])
    counts = _CATEGORY_COUNTS.get(normalized, _CATEGORY_COUNTS["technical"])
    items: list[QuestionPlanItem] = []
    for category in order:
        count = counts.get(category, 0)
        if count <= 0:
            continue
        difficulty = "advanced" if category in {"technical", "coding", "system_design", "architecture"} else "intermediate"
        priority = "must_prepare" if category in {"technical", "system_design", "behavioral", "resume_deep_dive"} else "high"
        items.append(QuestionPlanItem(category=category, count=count, difficulty=difficulty, priority=priority))
    return QuestionCoveragePlan(items=items)


class DeterministicInterviewQuestionGenerator:
    async def generate(
        self,
        context: QuestionGenerationContext,
        coverage_plan: QuestionCoveragePlan,
    ) -> list[GeneratedInterviewQuestion]:
        questions: list[GeneratedInterviewQuestion] = []
        category_indexes: dict[str, int] = {}
        for item in coverage_plan.items:
            for _ in range(item.count):
                question = _build_question_for_category(
                    context,
                    item.category,
                    index=category_indexes.get(item.category, 0),
                    difficulty=item.difficulty,
                    priority=item.priority,
                )
                category_indexes[item.category] = category_indexes.get(item.category, 0) + 1
                if question is not None:
                    questions.append(question)
        return questions


def generator_metadata() -> dict[str, object]:
    return {
        "provider": QUESTION_PROVIDER,
        "model_key": "",
        "strategy_version": QUESTION_STRATEGY_VERSION,
        "token_usage": None,
        "cost_usd": None,
    }


def _build_question_for_category(
    context: QuestionGenerationContext,
    category: str,
    *,
    index: int,
    difficulty: str,
    priority: str,
) -> GeneratedInterviewQuestion | None:
    dimensions = list(_EVALUATION_DIMENSIONS.get(category, ("clarity", "evidence usage")))
    focus_requirement = _cycle_value(context.focus_requirements, index)
    requirement_refs = list(context.job_requirement_evidence.get(focus_requirement, [])) if focus_requirement else []
    recruiter_line = _cycle_value(context.recruiter_context, index)
    company_line = _cycle_value(context.company_context, index)
    resume_claim = _cycle_value(context.resume_claims, index)
    project_example = _cycle_value(context.project_examples, index)
    leadership_example = _cycle_value(context.leadership_examples, index)
    architecture_example = _cycle_value(context.architecture_examples, index)
    risk_example = _cycle_value(context.risk_examples, index)

    if category == "technical":
        requirement = focus_requirement or "a core technical requirement from the role"
        prompt = f"Tell me about a production system where you used {requirement}. What constraints, tradeoffs, and outcomes mattered most?"
        rationale = f"Selected because {requirement} is a highlighted role signal and technical rounds usually probe concrete execution depth."
        evidence = requirement_refs or _example_evidence(project_example) or _example_evidence(resume_claim)
        outline = ["Frame the problem and production context.", "Explain your design or implementation decisions.", "Close with measurable results and lessons."]
        return _generated_question(
            category=category,
            prompt=prompt,
            rationale=rationale,
            dimensions=dimensions,
            requirements=[requirement] if focus_requirement else [],
            evidence=evidence,
            difficulty=difficulty,
            priority=priority,
            outline=outline,
            risk_tags=_example_risks(risk_example),
        )

    if category == "coding":
        requirement = focus_requirement or "backend engineering"
        prompt = f"If we gave you a coding problem related to {requirement}, how would you structure the solution, test it, and talk through tradeoffs as you go?"
        rationale = f"Selected because coding rounds evaluate reasoning quality, not just correctness, and {requirement} is part of the current role context."
        evidence = requirement_refs or _example_evidence(resume_claim) or _example_evidence(project_example)
        outline = ["Clarify assumptions before coding.", "Describe the core approach and edge cases.", "Explain test strategy and tradeoffs."]
        return _generated_question(
            category=category,
            prompt=prompt,
            rationale=rationale,
            dimensions=dimensions,
            requirements=[requirement] if focus_requirement else [],
            evidence=evidence,
            difficulty=difficulty,
            priority=priority,
            outline=outline,
            risk_tags=_example_risks(risk_example),
        )

    if category == "system_design":
        requirement = focus_requirement or "scalable backend systems"
        prompt = f"Design a system similar to the problems in this role where {requirement} matters. How would you handle scale, failure modes, and operational visibility?"
        rationale = f"Selected because system design rounds should map back to the role's actual platform concerns, including {requirement}."
        evidence = requirement_refs or _example_evidence(architecture_example) or _example_evidence(project_example)
        outline = ["Scope the problem and primary constraints.", "Describe the core architecture and tradeoffs.", "Cover observability, scaling, and failure handling."]
        return _generated_question(
            category=category,
            prompt=prompt,
            rationale=rationale,
            dimensions=dimensions,
            requirements=[requirement] if focus_requirement else [],
            evidence=evidence,
            difficulty=difficulty,
            priority=priority,
            outline=outline,
            risk_tags=_example_risks(risk_example),
        )

    if category == "architecture":
        example = architecture_example or project_example
        label = example.label if example is not None else "a system you have owned"
        prompt = f"Walk me through the architecture decisions behind {label}. Why did you choose that approach, and what would you change now?"
        rationale = "Selected because architecture rounds usually test decision quality, system constraints, and reflection on tradeoffs."
        evidence = _example_evidence(example) or requirement_refs or _example_evidence(resume_claim)
        outline = ["Summarize the architecture and constraints.", "Explain the critical design decisions.", "Reflect on tradeoffs, incidents, or future improvements."]
        return _generated_question(
            category=category,
            prompt=prompt,
            rationale=rationale,
            dimensions=dimensions,
            requirements=[focus_requirement] if focus_requirement else [],
            evidence=evidence,
            difficulty=difficulty,
            priority=priority,
            outline=outline,
            risk_tags=_example_risks(example) or _example_risks(risk_example),
        )

    if category == "behavioral":
        requirement = focus_requirement or "ownership"
        prompt = f"Tell me about a time you had to demonstrate {requirement} under ambiguity or pressure. What did you do, and what changed afterward?"
        rationale = f"Selected because behavioral evaluation should connect directly to role signals such as {requirement}, not generic storytelling."
        evidence = _example_evidence(leadership_example) or requirement_refs or _example_evidence(project_example)
        outline = ["Set the context and stakes.", "Explain your actions and decision process.", "Show the result and what you learned."]
        return _generated_question(
            category=category,
            prompt=prompt,
            rationale=rationale,
            dimensions=dimensions,
            requirements=[requirement] if focus_requirement else [],
            evidence=evidence,
            difficulty="intermediate",
            priority=priority,
            outline=outline,
            risk_tags=_example_risks(risk_example),
        )

    if category == "leadership":
        example = leadership_example or project_example
        label = example.label if example is not None else "a cross-functional initiative"
        prompt = f"Describe how you influenced outcomes on {label} when you did not control every dependency directly."
        rationale = "Selected because leadership questions should probe influence, stakeholder management, and judgment using verified examples."
        evidence = _example_evidence(example) or requirement_refs
        outline = ["Describe the stakeholders and constraints.", "Explain how you aligned people and decisions.", "Close with the outcome and what you would repeat or change."]
        return _generated_question(
            category=category,
            prompt=prompt,
            rationale=rationale,
            dimensions=dimensions,
            requirements=[focus_requirement] if focus_requirement else [],
            evidence=evidence,
            difficulty="advanced",
            priority=priority,
            outline=outline,
            risk_tags=_example_risks(example),
        )

    if category == "resume_deep_dive":
        claim = resume_claim
        if claim is None:
            detail = f"your submitted experience for {context.role_title}"
            requirements = [focus_requirement] if focus_requirement else []
            evidence = requirement_refs
            risk_tags = _example_risks(risk_example)
        else:
            detail = claim.detail
            requirements = list(claim.requirements)
            evidence = list(claim.evidence)
            risk_tags = list(claim.risk_tags)
        prompt = f"Your submitted resume says: \"{detail}\". Walk me through the real context, your role, and the measurable outcome."
        rationale = "Selected because resume deep-dive questions test whether submitted claims are accurate, specific, and evidence-backed."
        outline = ["State the business or technical context.", "Clarify exactly what you owned.", "Quantify the outcome and mention tradeoffs or lessons."]
        return _generated_question(
            category=category,
            prompt=prompt,
            rationale=rationale,
            dimensions=dimensions,
            requirements=requirements,
            evidence=evidence or requirement_refs,
            difficulty=difficulty,
            priority="must_prepare",
            outline=outline,
            risk_tags=risk_tags or _example_risks(risk_example),
        )

    if category == "project_deep_dive":
        example = project_example or architecture_example
        label = example.label if example is not None else "one of your most relevant production projects"
        prompt = f"Let’s go deeper on {label}. What problem were you solving, what was hardest technically, and what was the final impact?"
        rationale = "Selected because project deep-dives are the clearest way to connect job requirements to real execution evidence."
        evidence = _example_evidence(example) or requirement_refs or _example_evidence(resume_claim)
        outline = ["Explain the problem and why it mattered.", "Describe the hard technical or organizational part.", "End with concrete results and retrospection."]
        return _generated_question(
            category=category,
            prompt=prompt,
            rationale=rationale,
            dimensions=dimensions,
            requirements=[focus_requirement] if focus_requirement else [],
            evidence=evidence,
            difficulty=difficulty,
            priority=priority,
            outline=outline,
            risk_tags=_example_risks(example) or _example_risks(risk_example),
        )

    if category == "career_motivation":
        company = context.company or "the company"
        prompt = f"Why are you interested in {company} and this {context.role_title} role right now, and how does it fit the next step in your career?"
        rationale = "Selected because career motivation should be tailored to the actual company, role, and current application stage."
        evidence = requirement_refs or _example_evidence(resume_claim)
        outline = ["Explain why this role is a fit now.", "Connect your recent evidence to the role's needs.", "Show long-term alignment without sounding generic."]
        return _generated_question(
            category=category,
            prompt=prompt,
            rationale=rationale,
            dimensions=dimensions,
            requirements=[focus_requirement] if focus_requirement else [],
            evidence=evidence,
            difficulty="introductory",
            priority=priority,
            outline=outline,
            risk_tags=[],
        )

    if category == "company_specific":
        context_line = recruiter_line or company_line or f"{context.company} is evaluating you for {context.role_title}."
        prompt = f"What stands out to you about this role and company context: {context_line}"
        rationale = "Selected because company-specific questions should reflect the actual recruiter and application context already stored in the platform."
        evidence = requirement_refs or _example_evidence(resume_claim)
        outline = ["Reference the current company or process context.", "Connect that context to your experience.", "Explain how you would add value."]
        return _generated_question(
            category=category,
            prompt=prompt,
            rationale=rationale,
            dimensions=dimensions,
            requirements=[focus_requirement] if focus_requirement else [],
            evidence=evidence,
            difficulty="introductory",
            priority=priority,
            outline=outline,
            risk_tags=[],
        )

    if category == "recruiter_screen":
        recruiter_signal = recruiter_line or company_line or f"This application is for {context.role_title} at {context.company}."
        prompt = f"Give me the concise version of your background that best fits this opportunity. Use this context: {recruiter_signal}"
        rationale = "Selected because recruiter screens prioritize concise narrative fit and role alignment before deeper technical probing."
        evidence = requirement_refs or _example_evidence(resume_claim) or _example_evidence(project_example)
        outline = ["Summarize your background in one arc.", "Tie it directly to the role's needs.", "Close with why this opportunity fits now."]
        return _generated_question(
            category=category,
            prompt=prompt,
            rationale=rationale,
            dimensions=dimensions,
            requirements=[focus_requirement] if focus_requirement else [],
            evidence=evidence,
            difficulty="introductory",
            priority=priority,
            outline=outline,
            risk_tags=[],
        )

    if category == "product_judgment":
        prompt = f"How would you decide what to prioritize first if the role surfaced competing technical and user-impact concerns around {focus_requirement or context.role_title}?"
        rationale = "Selected because product judgment questions test prioritization and user impact without requiring a separate PM-specific subsystem."
        evidence = requirement_refs or _example_evidence(project_example)
        outline = ["Clarify the decision criteria.", "Balance user impact, technical risk, and delivery cost.", "Explain how you would validate the choice."]
        return _generated_question(
            category=category,
            prompt=prompt,
            rationale=rationale,
            dimensions=dimensions,
            requirements=[focus_requirement] if focus_requirement else [],
            evidence=evidence,
            difficulty="advanced",
            priority=priority,
            outline=outline,
            risk_tags=[],
        )

    if category == "domain_specific":
        requirement = focus_requirement or context.role_title
        prompt = f"What domain-specific constraints or edge cases matter most when working on {requirement}, and how have you handled them in real work?"
        rationale = "Selected because domain-specific questions should force translation from abstract skills to the actual problem space."
        evidence = requirement_refs or _example_evidence(project_example) or _example_evidence(resume_claim)
        outline = ["Name the domain constraints.", "Use a real example instead of theory.", "Explain what you learned or would watch for next time."]
        return _generated_question(
            category=category,
            prompt=prompt,
            rationale=rationale,
            dimensions=dimensions,
            requirements=[requirement] if focus_requirement else [],
            evidence=evidence,
            difficulty=difficulty,
            priority=priority,
            outline=outline,
            risk_tags=[],
        )

    if category == "candidate_questions":
        prompt = _cycle_value(context.candidate_question_prompts, index) or f"What should you ask the interviewer to better understand success in the {context.role_title} role?"
        rationale = "Selected because candidate questions are part of interview readiness and should be grounded in the current stage, team, and role."
        evidence = requirement_refs
        outline = ["Ask something specific to the team or role.", "Avoid generic culture questions first.", "Use the answer to clarify success signals or open concerns."]
        return _generated_question(
            category=category,
            prompt=prompt,
            rationale=rationale,
            dimensions=dimensions,
            requirements=[focus_requirement] if focus_requirement else [],
            evidence=evidence,
            difficulty="introductory",
            priority="high",
            outline=outline,
            risk_tags=[],
        )

    return None


def _generated_question(
    *,
    category: str,
    prompt: str,
    rationale: str,
    dimensions: list[str],
    requirements: list[str],
    evidence: list[InterviewPreparationEvidenceReference],
    difficulty: str,
    priority: str,
    outline: list[str],
    risk_tags: list[str],
) -> GeneratedInterviewQuestion:
    normalized_requirements = [item.strip() for item in requirements if item and item.strip()]
    follow_ups = _default_follow_ups(category, prompt, requirements=normalized_requirements)
    return GeneratedInterviewQuestion(
        category=category,
        question=prompt,
        rationale=rationale,
        evaluation_dimensions=dimensions,
        related_job_requirements=normalized_requirements,
        related_evidence=evidence[:3],
        follow_up_questions=follow_ups[: QUESTION_SET_LIMITS["max_follow_ups"]],
        difficulty=difficulty if difficulty in QUESTION_DIFFICULTIES else "intermediate",
        priority=priority if priority in QUESTION_PRIORITIES else "medium",
        confidence=_confidence_from_evidence(evidence, risk_tags=risk_tags, category=category),
        expected_answer_outline=outline,
        risk_tags=[item for item in risk_tags if item.strip()],
    )


def _default_follow_ups(category: str, prompt: str, *, requirements: list[str]) -> list[InterviewQuestionFollowUp]:
    anchors = requirements[:1]
    requirement_text = anchors[0] if anchors else "that example"
    prompts = {
        "technical": (
            f"What tradeoff did you have to make around {requirement_text}?",
            "What would you change if you had to do it again?",
        ),
        "coding": (
            "What edge cases did you consider first?",
            "How would you test the solution under production constraints?",
        ),
        "system_design": (
            "Where would the first bottleneck or failure mode likely appear?",
            "How would you evolve the design as scale or requirements changed?",
        ),
        "behavioral": (
            "What was hardest about the situation personally or organizationally?",
            "What would your stakeholders say you handled well or poorly?",
        ),
        "resume_deep_dive": (
            "What part of that claim is most likely to be misunderstood without context?",
            "How did you measure whether the work actually succeeded?",
        ),
        "candidate_questions": (
            "Why is this question useful at this stage of the process?",
            "What follow-up would you ask if the answer sounded vague?",
        ),
    }
    category_prompts = prompts.get(
        category,
        (
            f"What is the most important detail behind {requirement_text}?",
            "What would you emphasize differently in a shorter answer?",
        ),
    )
    items: list[InterviewQuestionFollowUp] = []
    for index, item in enumerate(category_prompts, start=1):
        items.append(
            InterviewQuestionFollowUp(
                follow_up_id=str(uuid5(NAMESPACE_URL, f"{category}:{prompt}:{index}")),
                question=item,
                rationale="Reusable follow-up for deeper probing in later mock interview workflows.",
                evaluation_dimensions=list(_EVALUATION_DIMENSIONS.get(category, ("clarity",))),
                confidence=0.7,
            )
        )
    return items


def _confidence_from_evidence(
    evidence: list[InterviewPreparationEvidenceReference],
    *,
    risk_tags: list[str],
    category: str,
) -> float:
    if evidence:
        average = sum(max(0.0, min(1.0, item.confidence)) for item in evidence) / len(evidence)
    else:
        average = 0.52
    if risk_tags:
        average -= 0.08
    if category in {"candidate_questions", "career_motivation", "company_specific"}:
        average += 0.05
    return round(max(0.35, min(0.96, average)), 3)


def _cycle_value[T](values: list[T], index: int) -> T | None:
    if not values:
        return None
    return values[index % len(values)]


def _example_evidence(example: QuestionExample | ResumeClaim | None) -> list[InterviewPreparationEvidenceReference]:
    if example is None:
        return []
    return list(example.evidence)


def _example_risks(example: QuestionExample | ResumeClaim | None) -> list[str]:
    if example is None:
        return []
    return [item.strip() for item in example.risk_tags if item and item.strip()]
