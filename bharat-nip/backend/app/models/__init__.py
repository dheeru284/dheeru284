"""All ORM models. Importing this package registers every table on ``Base.metadata``."""

from app.models.ai import AIRun, PipelineJob
from app.models.assessments import Assessment, AssessmentCitation, Critique
from app.models.audit import AuditEvent
from app.models.claims import Claim, Entity, Submission
from app.models.evidence import Evidence, EvidenceRanking
from app.models.review import ReviewDecision, ReviewTask
from app.models.sources import Publisher, RetrievalResult, Source, SourceChunk
from app.models.users import User

__all__ = [
    "AIRun",
    "Assessment",
    "AssessmentCitation",
    "AuditEvent",
    "Claim",
    "Critique",
    "Entity",
    "Evidence",
    "EvidenceRanking",
    "PipelineJob",
    "Publisher",
    "RetrievalResult",
    "ReviewDecision",
    "ReviewTask",
    "Source",
    "SourceChunk",
    "Submission",
    "User",
]
