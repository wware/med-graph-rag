from pydantic import BaseModel, Field
from typing import List, Optional


class BaseMedicalRelationship(BaseModel):
    """
    Base class for all medical relationships with comprehensive provenance tracking.

    All medical relationships inherit from this class and include evidence-based
    provenance fields to support confidence scoring, contradiction detection,
    and temporal tracking of medical knowledge.

    Attributes:
        subject_id: Entity ID of the subject (source node)
        predicate: Relationship type name
        object_id: Entity ID of the object (target node)
        source_papers: List of PMC IDs supporting this relationship
        confidence: Confidence score (0.0-1.0) based on evidence strength
        evidence_count: Number of papers providing supporting evidence
        contradicted_by: List of PMC IDs with contradicting findings
        first_reported: Date when this relationship was first observed
        last_updated: Date of most recent supporting evidence

    Example:
        >>> relationship = Treats(
        ...     subject_id="RxNorm:1187832",
        ...     predicate="TREATS",
        ...     object_id="C0006142",
        ...     source_papers=["PMC123", "PMC456"],
        ...     confidence=0.85,
        ...     evidence_count=2,
        ...     response_rate=0.59
        ... )
    """

    subject_id: str
    predicate: str
    object_id: str

    # Provenance - required for all medical relationships
    source_papers: List[str] = Field(
        default_factory=list
    )  # PMC IDs supporting this relationship
    confidence: float = 0.5  # 0.0-1.0 based on evidence strength

    # Evidence tracking
    evidence_count: int = 0  # Number of papers supporting
    contradicted_by: List[str] = Field(
        default_factory=list
    )  # PMC IDs of contradicting papers
    first_reported: Optional[str] = None  # Date first observed
    last_updated: Optional[str] = None  # Most recent evidence


class Causes(BaseMedicalRelationship):
    """
    Represents a causal relationship between a disease and a symptom.

    Direction: Disease -> Symptom

    Attributes:
        frequency: How often the symptom occurs (always, often, sometimes, rarely)
        onset: When the symptom typically appears (early, late)
        severity: Typical severity of the symptom

    Example:
        >>> causes = Causes(
        ...     subject_id="C0006142",  # Breast Cancer
        ...     predicate="CAUSES",
        ...     object_id="C0030193",  # Pain
        ...     frequency="often",
        ...     onset="late",
        ...     severity="moderate",
        ...     source_papers=["PMC123"],
        ...     confidence=0.75
        ... )
    """

    frequency: Optional[str] = None  # always, often, sometimes, rarely
    onset: Optional[str] = None  # early, late
    severity: Optional[str] = None  # Typical severity


class Treats(BaseMedicalRelationship):
    """
    Represents a therapeutic relationship between a drug and a disease.

    Direction: Drug -> Disease

    Attributes:
        efficacy: Effectiveness measure or description
        response_rate: Percentage of patients responding (0.0-1.0)
        line_of_therapy: Treatment sequence (first-line, second-line, etc.)
        indication: Specific approved use or condition

    Example:
        >>> treats = Treats(
        ...     subject_id="RxNorm:1187832",  # Olaparib
        ...     predicate="TREATS",
        ...     object_id="C0006142",  # Breast Cancer
        ...     efficacy="significant improvement in PFS",
        ...     response_rate=0.59,
        ...     line_of_therapy="second-line",
        ...     indication="BRCA-mutated breast cancer",
        ...     source_papers=["PMC999", "PMC888"],
        ...     confidence=0.85
        ... )
    """

    efficacy: Optional[str] = None  # Effectiveness measure
    response_rate: Optional[float] = None  # 0.0-1.0 percentage of patients responding
    line_of_therapy: Optional[str] = None  # first-line, second-line, etc.
    indication: Optional[str] = None  # Specific approved use


class IncreasesRisk(BaseMedicalRelationship):
    """
    Represents genetic risk factors for diseases.

    Direction: Gene/Mutation -> Disease

    Attributes:
        risk_ratio: Numeric risk increase (e.g., 2.5 means 2.5x higher risk)
        penetrance: Percentage who develop condition (0.0-1.0)
        age_of_onset: Typical age when disease manifests
        population: Studied population or ethnic group

    Example:
        >>> risk = IncreasesRisk(
        ...     subject_id="HGNC:1100",  # BRCA1
        ...     predicate="INCREASES_RISK",
        ...     object_id="C0006142",  # Breast Cancer
        ...     risk_ratio=5.0,
        ...     penetrance=0.72,
        ...     age_of_onset="40-50 years",
        ...     population="Ashkenazi Jewish",
        ...     source_papers=["PMC123", "PMC456"],
        ...     confidence=0.92
        ... )
    """

    risk_ratio: Optional[float] = None  # Numeric risk increase (e.g., 2.5x)
    penetrance: Optional[float] = None  # 0.0-1.0 percentage who develop condition
    age_of_onset: Optional[str] = None  # Typical age
    population: Optional[str] = None  # Studied population


class AssociatedWith(BaseMedicalRelationship):
    """
    Represents a general association between entities.

    This is used for relationships where causality is not established but
    statistical association exists.

    Valid directions:
        - Disease -> Disease (comorbidities)
        - Gene -> Disease
        - Biomarker -> Disease

    Attributes:
        association_type: Nature of association (positive, negative, neutral)
        strength: Association strength (strong, moderate, weak)
        statistical_significance: p-value from statistical tests

    Example:
        >>> assoc = AssociatedWith(
        ...     subject_id="C0011849",  # Diabetes
        ...     predicate="ASSOCIATED_WITH",
        ...     object_id="C0020538",  # Hypertension
        ...     association_type="positive",
        ...     strength="strong",
        ...     statistical_significance=0.001,
        ...     source_papers=["PMC111"],
        ...     confidence=0.80
        ... )
    """

    association_type: Optional[str] = None  # positive, negative, neutral
    strength: Optional[str] = None  # strong, moderate, weak
    statistical_significance: Optional[float] = None  # p-value


class InteractsWith(BaseMedicalRelationship):
    """
    Represents drug-drug interactions.

    Direction: Drug <-> Drug (bidirectional)

    Attributes:
        interaction_type: Nature of interaction (synergistic, antagonistic, additive)
        severity: Clinical severity (major, moderate, minor)
        mechanism: Pharmacological mechanism of interaction
        clinical_significance: Description of clinical implications

    Example:
        >>> interaction = InteractsWith(
        ...     subject_id="RxNorm:123",  # Warfarin
        ...     predicate="INTERACTS_WITH",
        ...     object_id="RxNorm:456",  # Aspirin
        ...     interaction_type="synergistic",
        ...     severity="major",
        ...     mechanism="Additive anticoagulant effect",
        ...     clinical_significance="Increased bleeding risk",
        ...     source_papers=["PMC789"],
        ...     confidence=0.90
        ... )
    """

    interaction_type: Optional[str] = None  # synergistic, antagonistic, additive
    severity: Optional[str] = None  # major, moderate, minor
    mechanism: Optional[str] = None  # How they interact
    clinical_significance: Optional[str] = None  # Description


class Encodes(BaseMedicalRelationship):
    """
    Gene -[ENCODES]-> Protein
    """

    transcript_variants: Optional[int] = None  # Number of variants
    tissue_specificity: Optional[str] = None  # Where expressed


class ParticipatesIn(BaseMedicalRelationship):
    """
    Gene/Protein -[PARTICIPATES_IN]-> Pathway
    """

    role: Optional[str] = None  # Function in pathway
    regulatory_effect: Optional[str] = None  # activates, inhibits, modulates


class ContraindicatedFor(BaseMedicalRelationship):
    """
    Drug -[CONTRAINDICATED_FOR]-> Disease/Condition
    """

    severity: Optional[str] = None  # absolute, relative
    reason: Optional[str] = None  # Why contraindicated


class DiagnosedBy(BaseMedicalRelationship):
    """
    Represents diagnostic tests or biomarkers used to diagnose a disease.

    Direction: Disease -> Procedure/Biomarker

    Attributes:
        sensitivity: True positive rate (0.0-1.0)
        specificity: True negative rate (0.0-1.0)
        standard_of_care: Whether this is standard clinical practice

    Example:
        >>> diagnosis = DiagnosedBy(
        ...     subject_id="C0006142",  # Breast Cancer
        ...     predicate="DIAGNOSED_BY",
        ...     object_id="LOINC:123",  # Mammography
        ...     sensitivity=0.87,
        ...     specificity=0.91,
        ...     standard_of_care=True,
        ...     source_papers=["PMC555"],
        ...     confidence=0.88
        ... )
    """

    sensitivity: Optional[float] = None  # 0.0-1.0 true positive rate
    specificity: Optional[float] = None  # 0.0-1.0 true negative rate
    standard_of_care: bool = False  # Whether this is standard practice


class SideEffect(BaseMedicalRelationship):
    """
    Represents adverse effects of medications.

    Direction: Drug -> Symptom

    Attributes:
        frequency: How often it occurs (common, uncommon, rare)
        severity: Severity level (mild, moderate, severe)
        reversible: Whether the side effect resolves after stopping the drug

    Example:
        >>> side_effect = SideEffect(
        ...     subject_id="RxNorm:1187832",  # Olaparib
        ...     predicate="SIDE_EFFECT",
        ...     object_id="C0027497",  # Nausea
        ...     frequency="common",
        ...     severity="mild",
        ...     reversible=True,
        ...     source_papers=["PMC999"],
        ...     confidence=0.75
        ... )
    """

    frequency: Optional[str] = None  # common, uncommon, rare
    severity: Optional[str] = None  # mild, moderate, severe
    reversible: bool = True  # Whether side effect is reversible


### Research Metadata Relationships


class ResearchRelationship(BaseModel):
    """
    Base class for research metadata relationships.

    These relationships connect papers, authors, and clinical trials.
    Unlike medical relationships, they don't require provenance tracking
    since they represent bibliographic metadata rather than medical claims.

    Attributes:
        subject_id: ID of the subject entity
        predicate: Relationship type
        object_id: ID of the object entity
    """

    subject_id: str
    predicate: str
    object_id: str


class CitedBy(ResearchRelationship):
    """
    Paper -[CITED_BY]-> Paper
    """

    context: Optional[str] = None  # What section the citation appears in
    sentiment: Optional[str] = None  # supports, contradicts, mentions


class Cites(ResearchRelationship):
    """
    Represents a citation from one paper to another.

    Direction: Paper -> Paper (citing -> cited)

    Attributes:
        context: Section where citation appears (introduction, methods, discussion)
        sentiment: How the citation is used (supports, contradicts, mentions)

    Example:
        >>> citation = Cites(
        ...     subject_id="PMC123",
        ...     predicate="CITES",
        ...     object_id="PMC456",
        ...     context="discussion",
        ...     sentiment="supports"
        ... )
    """

    context: Optional[str] = None  # What section the citation appears in
    sentiment: Optional[str] = None  # supports, contradicts, mentions


class StudiedIn(ResearchRelationship):
    """
    Links medical entities to papers that study them.

    Direction: Any medical entity -> Paper

    Attributes:
        role: Importance in the paper (primary_focus, secondary_finding, mentioned)
        section: Where discussed (results, methods, discussion, introduction)

    Example:
        >>> studied = StudiedIn(
        ...     subject_id="RxNorm:1187832",  # Olaparib
        ...     predicate="STUDIED_IN",
        ...     object_id="PMC999",
        ...     role="primary_focus",
        ...     section="results"
        ... )
    """

    role: Optional[str] = None  # primary_focus, secondary_finding, mentioned
    section: Optional[str] = None  # Where discussed (results, methods, discussion)


class AuthoredBy(ResearchRelationship):
    """
    Paper -[AUTHORED_BY]-> Author
    """

    position: Optional[str] = None  # first, last, corresponding, middle


class PartOf(ResearchRelationship):
    """
    Paper -[PART_OF]-> ClinicalTrial
    """

    publication_type: Optional[str] = None  # protocol, results, analysis
