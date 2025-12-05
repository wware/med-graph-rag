"""
## Overview

This schema is designed to support clinical decision-making by representing medical knowledge
extracted from research papers. The graph enables multi-hop reasoning, contradiction detection,
and evidence-based inference. It uses strongly-typed entity classes (Disease, Gene, Drug,
Protein, etc.) as the canonical representation for all entities in the knowledge graph.
This approach provides type safety and validation.

## Design Principles

1. **Clinical utility first** - Schema supports queries doctors actually ask
2. **Provenance always** - Every relationship traces back to source papers
3. **Handle uncertainty** - Represent confidence, contradictions, and evolution over time
4. **Standards-based** - Use UMLS, MeSH, and other medical ontologies for entity IDs
5. **Scalable** - Can grow from thousands to millions of papers

All medical entities (Disease, Gene, Drug, Protein, etc.) share these base properties:

- entity_id: Unique identifier (type-specific, e.g., UMLS ID, HGNC ID)
- name: Primary canonical name
- synonyms: [list of alternate names]
- abbreviations: [common abbreviations, e.g., "T2DM", "NIDDM"]
- embedding: Pre-computed biomedical embedding vector
- created_at: Timestamp when entity was added
- source: Origin ("umls", "mesh", "rxnorm", "hgnc", "uniprot", "extracted")
"""

import json
import boto3
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime
from tqdm import tqdm


class BaseMedicalEntity(BaseModel):
    """
    Base class for all medical entities in the knowledge graph.

    Serves as the canonical entity representation with external ontology mappings,
    pre-computed embeddings for semantic search, and provenance tracking.
    All specific entity types (Disease, Gene, Drug, etc.) inherit from this class.

    Attributes:
        entity_id: Unique identifier (e.g., UMLS ID, HGNC ID, RxNorm ID)
        name: Primary canonical name for the entity
        synonyms: Alternative names and variants
        abbreviations: Common abbreviations (e.g., "T2DM" for Type 2 Diabetes)
        embedding: Pre-computed biomedical embedding, 768? dimensions
        created_at: Timestamp when entity was added to the system
        source: Origin of this entity (umls, mesh, rxnorm, extracted)

    Example:
        >>> disease = Disease(
        ...     entity_id="C0011860",
        ...     name="Type 2 Diabetes Mellitus",
        ...     synonyms=["Type II Diabetes", "Adult-Onset Diabetes"],
        ...     abbreviations=["T2DM", "NIDDM"],
        ...     source="umls"
        ... )
    """

    entity_id: str
    name: str
    synonyms: List[str] = Field(default_factory=list)
    abbreviations: List[str] = Field(default_factory=list)

    # Embeddings for semantic search (pre-computed)
    embedding: Optional[List[float]] = None  # 768-dim

    # Metadata for provenance tracking
    created_at: datetime = Field(default_factory=datetime.now)
    source: str = (
        "extracted"  # "umls", "mesh", "rxnorm", "hgnc", "uniprot", "extracted"
    )


class Disease(BaseMedicalEntity):
    """
    Represents medical conditions, disorders, and syndromes.

    Uses UMLS as the primary identifier system with additional mappings to
    MeSH and ICD-10 for interoperability with clinical systems.

    Attributes:
        umls_id: UMLS Concept ID (e.g., "C0006142" for Breast Cancer)
        mesh_id: Medical Subject Heading ID for literature indexing
        icd10_codes: List of ICD-10 diagnostic codes
        category: Disease classification (genetic, infectious, autoimmune, etc.)

    Example:
        >>> breast_cancer = Disease(
        ...     entity_id="C0006142",
        ...     name="Breast Cancer",
        ...     synonyms=["Breast Carcinoma", "Mammary Cancer"],
        ...     umls_id="C0006142",
        ...     mesh_id="D001943",
        ...     icd10_codes=["C50.9"],
        ...     category="genetic"
        ... )
    """

    umls_id: Optional[str] = (
        None  # UMLS Concept ID (e.g., C0006142 for "Breast Cancer")
    )
    mesh_id: Optional[str] = None
    icd10_codes: List[str] = Field(default_factory=list)
    category: Optional[str] = None  # genetic, infectious, autoimmune, etc.


class Gene(BaseMedicalEntity):
    """
    Represents genes and their genomic information.

    Uses HGNC (HUGO Gene Nomenclature Committee) as the primary identifier
    with additional mappings to NCBI Entrez Gene.

    Attributes:
        symbol: Official gene symbol (e.g., "BRCA1")
        hgnc_id: HGNC identifier (e.g., "HGNC:1100")
        chromosome: Chromosomal location (e.g., "17q21.31")
        entrez_id: NCBI Gene ID for cross-referencing

    Example:
        >>> brca1 = Gene(
        ...     entity_id="HGNC:1100",
        ...     name="BRCA1 DNA repair associated",
        ...     synonyms=["BRCA1", "breast cancer 1"],
        ...     symbol="BRCA1",
        ...     hgnc_id="HGNC:1100",
        ...     chromosome="17q21.31",
        ...     entrez_id="672"
        ... )
    """

    symbol: Optional[str] = None  # Gene symbol (e.g., BRCA1)
    hgnc_id: Optional[str] = None  # HGNC ID (e.g., HGNC:1100)
    chromosome: Optional[str] = None  # Location (e.g., 17q21.31)
    entrez_id: Optional[str] = None  # NCBI Gene ID


class Mutation(BaseMedicalEntity):
    """
    Represents specific genetic variants
    """

    gene_id: Optional[str] = None
    variant_type: Optional[str] = None
    notation: Optional[str] = None
    consequence: Optional[str] = None


class Drug(BaseMedicalEntity):
    """
    Represents medications and therapeutic substances.

    Uses RxNorm as the primary identifier for standardized medication naming.

    Attributes:
        rxnorm_id: RxNorm Concept ID for drug identification
        brand_names: List of commercial/brand names
        drug_class: Therapeutic class (chemotherapy, immunotherapy, etc.)
        mechanism: Mechanism of action description

    Example:
        >>> olaparib = Drug(
        ...     entity_id="RxNorm:1187832",
        ...     name="Olaparib",
        ...     synonyms=["AZD2281"],
        ...     rxnorm_id="1187832",
        ...     brand_names=["Lynparza"],
        ...     drug_class="PARP inhibitor",
        ...     mechanism="Inhibits poly ADP-ribose polymerase enzymes"
        ... )
    """

    rxnorm_id: Optional[str] = None
    brand_names: Optional[List[str]] = None
    drug_class: Optional[str] = None
    mechanism: Optional[str] = None


class Protein(BaseMedicalEntity):
    """
    Represents proteins and their biological functions.

    Uses UniProt as the primary identifier for protein sequences and annotations.

    Attributes:
        uniprot_id: UniProt accession number
        gene_id: ID of the gene that encodes this protein
        function: Description of biological function
        pathways: List of biological pathways this protein participates in

    Example:
        >>> brca1_protein = Protein(
        ...     entity_id="P38398",
        ...     name="Breast cancer type 1 susceptibility protein",
        ...     synonyms=["BRCA1"],
        ...     uniprot_id="P38398",
        ...     gene_id="HGNC:1100",
        ...     function="DNA repair and tumor suppression",
        ...     pathways=["DNA damage response", "Homologous recombination"]
        ... )
    """

    uniprot_id: Optional[str] = None  # UniProt ID
    gene_id: Optional[str] = None  # Encoding gene
    function: Optional[str] = None  # Biological function
    pathways: List[str] = Field(default_factory=list)  # Biological pathways involved in


class Symptom(BaseMedicalEntity):
    """
    Represents clinical signs and symptoms
    """

    severity_scale: Optional[str] = None


class Procedure(BaseMedicalEntity):
    """
    Represents medical tests, diagnostics, treatments
    """

    type: Optional[str] = None
    invasiveness: Optional[str] = None


class Biomarker(BaseMedicalEntity):
    """
    Represents measurable indicators
    """

    loinc_code: Optional[str] = None  # LOINC code
    measurement_type: Optional[str] = None  # blood, tissue, imaging
    normal_range: Optional[str] = None  # Reference values


class Pathway(BaseMedicalEntity):
    """
    Represents biological pathways
    """

    kegg_id: Optional[str] = None  # KEGG ID
    reactome_id: Optional[str] = None  # Reactome ID
    category: Optional[str] = None  # signaling, metabolic, etc.
    genes_involved: List[str] = Field(default_factory=list)


### Research Metadata Nodes


class Paper(BaseModel):
    """
    Represents a research paper in the medical literature.

    Stores metadata about scientific publications including identifiers,
    bibliographic information, and study characteristics used for evidence
    quality assessment and provenance tracking.

    Attributes:
        pmc_id: PubMed Central ID (primary identifier)
        pmid: PubMed ID for cross-referencing
        doi: Digital Object Identifier
        title: Full paper title
        abstract: Complete abstract text
        authors: List of author names
        journal: Journal name
        publication_date: Publication date (ISO format recommended)
        study_type: Type of study (RCT, cohort, case-control, review, meta-analysis)
        sample_size: Number of subjects/participants
        mesh_terms: Medical Subject Headings for indexing

    Example:
        >>> paper = Paper(
        ...     pmc_id="PMC123456",
        ...     pmid="12345678",
        ...     doi="10.1234/example",
        ...     title="Efficacy of Drug X in Disease Y",
        ...     abstract="This randomized controlled trial...",
        ...     authors=["Smith J", "Doe A"],
        ...     journal="New England Journal of Medicine",
        ...     publication_date="2023-01-15",
        ...     study_type="RCT",
        ...     sample_size=500,
        ...     mesh_terms=["Breast Neoplasms", "Drug Therapy"]
        ... )
    """

    pmc_id: str  # PubMed Central ID
    pmid: Optional[str] = None  # PubMed ID
    doi: Optional[str] = None  # Digital Object Identifier
    title: str
    abstract: str
    authors: List[str] = Field(default_factory=list)
    journal: str
    publication_date: Optional[str] = None  # Date published
    study_type: Optional[str] = None  # RCT, cohort, case-control, review, meta-analysis
    sample_size: Optional[int] = None  # Number of subjects
    mesh_terms: List[str] = Field(default_factory=list)  # Medical Subject Headings


class Author(BaseModel):
    """
    Represents a researcher or author of scientific publications.

    Attributes:
        orcid: ORCID identifier (unique researcher ID)
        name: Full name of the researcher
        affiliations: List of institutional affiliations
        h_index: Citation metric indicating research impact

    Example:
        >>> author = Author(
        ...     orcid="0000-0001-2345-6789",
        ...     name="Jane Smith",
        ...     affiliations=["Harvard Medical School", "Massachusetts General Hospital"],
        ...     h_index=45
        ... )
    """

    orcid: str  # ORCID identifier
    name: str  # Full name
    affiliations: List[str] = Field(default_factory=list)  # Institutions
    h_index: Optional[int] = None  # Citation metric


class ClinicalTrial(BaseModel):
    """
    Represents a clinical trial registered on ClinicalTrials.gov.

    Attributes:
        nct_id: ClinicalTrials.gov identifier (e.g., "NCT01234567")
        title: Official trial title
        phase: Trial phase (I, II, III, IV)
        status: Current status (recruiting, completed, terminated, etc.)
        intervention: Description of treatment being tested

    Example:
        >>> trial = ClinicalTrial(
        ...     nct_id="NCT01234567",
        ...     title="Study of Drug X in Patients with Disease Y",
        ...     phase="III",
        ...     status="completed",
        ...     intervention="Drug X 100mg daily"
        ... )
    """

    nct_id: str  # ClinicalTrials.gov identifier
    title: str  # Trial title
    phase: Optional[str] = None  # I, II, III, IV
    status: Optional[str] = None  # recruiting, completed, etc.
    intervention: Optional[str] = None  # Treatment being tested


class ExtractedEntity(BaseModel):
    """
    Represents a single entity mention extracted from a paper.

    Captures the exact text span where an entity was mentioned, along with
    its position and the confidence of the extraction model. Links to the
    canonical typed entity (Disease, Gene, Drug, etc.).

    Attributes:
        mention_text: Exact text as it appears in the paper (e.g., "T2DM")
        canonical_id: ID of the canonical entity (e.g., UMLS ID, HGNC ID)
        entity_type: Type of entity (disease, drug, gene, etc.)
        start_char: Character offset where mention starts
        end_char: Character offset where mention ends
        chunk_id: Identifier of the text chunk containing this mention
        confidence: Extraction confidence score (0.0-1.0)
        extraction_method: Name of the NER model used (biobert, scispacy, etc.)
    """

    mention_text: str  # "T2DM"
    canonical_id: str  # Links to canonical entity ID (e.g., "C0011860")
    entity_type: str  # "disease"

    # Position in text
    start_char: int
    end_char: int
    chunk_id: str  # Which chunk this came from

    # Extraction metadata
    confidence: float  # 0.0-1.0 from NER model
    extraction_method: str  # "biobert", "scispacy", etc.


class EntityMention(BaseModel):
    """
    Aggregated view of an entity across all its mentions in a paper.

    Combines multiple ExtractedEntity instances that refer to the same
    canonical entity, providing a paper-level summary.

    Attributes:
        entity_id: Canonical entity ID (e.g., UMLS ID, HGNC ID)
        canonical_name: Normalized name of the entity
        entity_type: Type of entity (disease, drug, gene, etc.)
        mention_count: Total number of times mentioned in the paper
        mentions: List of all text variants used (e.g., ["T2DM", "type 2 diabetes"])
        chunk_ids: IDs of chunks where this entity appears
    """

    entity_id: str  # Canonical entity ID (e.g., "C0011860")
    canonical_name: str  # "Type 2 Diabetes Mellitus"
    entity_type: str
    mention_count: int  # How many times mentioned
    mentions: List[str]  # ["T2DM", "type 2 diabetes", ...]
    chunk_ids: List[str]  # Which chunks mention this entity


class Relationship(BaseModel):
    """
    Represents a relationship between two entities extracted from a paper.

    Captures semantic relationships like "Drug X treats Disease Y" with
    supporting evidence and extraction metadata.

    Attributes:
        subject_id: Canonical entity ID of the subject (e.g., RxNorm ID for drug)
        predicate: Relationship type (TREATS, CAUSES, ASSOCIATED_WITH, etc.)
        object_id: Canonical entity ID of the object (e.g., UMLS ID for disease)
        evidence_text: Sentence or paragraph supporting this relationship
        chunk_id: ID of the chunk containing the evidence
        confidence: Confidence score (0.0-1.0)
        extraction_method: How this was extracted (cooccurrence, relationship_extraction)
    """

    subject_id: str  # Canonical entity ID (e.g., "RxNorm:1187832")
    predicate: str  # "TREATS", "CAUSES", "ASSOCIATED_WITH"
    object_id: str  # Canonical entity ID (e.g., "C0006142")

    # Evidence
    evidence_text: str  # Sentence/paragraph where found
    chunk_id: str
    confidence: float = 0.5  # Start with co-occurrence confidence

    # Provenance
    extraction_method: str  # "cooccurrence", "relationship_extraction"


# ========== Paper Output ==========


class ProcessedPaper(BaseModel):
    """
    Complete processed paper ready for insertion into the knowledge graph.

    Represents the final output of the paper processing pipeline, containing
    all extracted entities, relationships, and metadata.

    Attributes:
        pmc_id: PubMed Central ID
        pmid: PubMed ID
        doi: Digital Object Identifier
        title: Paper title
        abstract: Full abstract
        authors: List of author names
        publication_date: Publication date
        journal: Journal name
        entities: All entities mentioned in the paper
        relationships: All relationships extracted from the paper
        processed_at: Timestamp when processing completed
        entity_count: Total number of unique entities
        relationship_count: Total number of relationships
        full_text: Complete paper text for indexing
    """

    # Metadata (from JATS parser)
    pmc_id: str
    pmid: Optional[str]
    doi: Optional[str]
    title: str
    abstract: str
    authors: List[str]
    publication_date: Optional[str]
    journal: str

    # Extracted entities
    entities: List[EntityMention]

    # Extracted relationships
    relationships: List[Relationship]

    # Processing metadata
    processed_at: datetime = Field(default_factory=datetime.now)
    entity_count: int
    relationship_count: int

    # Full text for indexing
    full_text: str


# ========== Reference Entity Collection ==========


class EntityCollection(BaseModel):
    """
    Collection of canonical entities organized by type.

    Manages the master set of normalized entities that extracted mentions
    are linked to. Stores typed entities (Disease, Gene, Drug, etc.) with
    methods for adding, querying, and persisting the collection.

    Attributes:
        diseases: Dictionary mapping entity_id to Disease entities
        genes: Dictionary mapping entity_id to Gene entities
        drugs: Dictionary mapping entity_id to Drug entities
        proteins: Dictionary mapping entity_id to Protein entities
        symptoms: Dictionary mapping entity_id to Symptom entities
        procedures: Dictionary mapping entity_id to Procedure entities
        biomarkers: Dictionary mapping entity_id to Biomarker entities
        pathways: Dictionary mapping entity_id to Pathway entities
        version: Version identifier for the collection
        created_at: Timestamp when collection was created
    """

    diseases: Dict[str, Disease] = Field(default_factory=dict)
    genes: Dict[str, Gene] = Field(default_factory=dict)
    drugs: Dict[str, Drug] = Field(default_factory=dict)
    proteins: Dict[str, Protein] = Field(default_factory=dict)
    symptoms: Dict[str, Symptom] = Field(default_factory=dict)
    procedures: Dict[str, Procedure] = Field(default_factory=dict)
    biomarkers: Dict[str, Biomarker] = Field(default_factory=dict)
    pathways: Dict[str, Pathway] = Field(default_factory=dict)

    version: str = "v1"
    created_at: datetime = Field(default_factory=datetime.now)

    @property
    def entity_count(self) -> int:
        """Total number of entities across all types"""
        return (
            len(self.diseases)
            + len(self.genes)
            + len(self.drugs)
            + len(self.proteins)
            + len(self.symptoms)
            + len(self.procedures)
            + len(self.biomarkers)
            + len(self.pathways)
        )

    def add_disease(self, entity: Disease):
        """Add a disease entity to the collection"""
        self.diseases[entity.entity_id] = entity

    def add_gene(self, entity: Gene):
        """Add a gene entity to the collection"""
        self.genes[entity.entity_id] = entity

    def add_drug(self, entity: Drug):
        """Add a drug entity to the collection"""
        self.drugs[entity.entity_id] = entity

    def add_protein(self, entity: Protein):
        """Add a protein entity to the collection"""
        self.proteins[entity.entity_id] = entity

    def get_by_id(self, entity_id: str) -> Optional[BaseMedicalEntity]:
        """Get entity by ID, searching across all types"""
        for collection in [
            self.diseases,
            self.genes,
            self.drugs,
            self.proteins,
            self.symptoms,
            self.procedures,
            self.biomarkers,
            self.pathways,
        ]:
            if entity_id in collection:
                return collection[entity_id]
        return None

    def get_by_umls(self, umls_id: str) -> Optional[Disease]:
        """Get disease by UMLS ID"""
        for entity in self.diseases.values():
            if entity.umls_id == umls_id:
                return entity
        return None

    def get_by_hgnc(self, hgnc_id: str) -> Optional[Gene]:
        """Get gene by HGNC ID"""
        for entity in self.genes.values():
            if entity.hgnc_id == hgnc_id:
                return entity
        return None

    def save(self, path: str):
        """Save to JSONL with type information"""
        with open(path, "w") as f:
            for entity_type, collection in [
                ("disease", self.diseases),
                ("gene", self.genes),
                ("drug", self.drugs),
                ("protein", self.proteins),
                ("symptom", self.symptoms),
                ("procedure", self.procedures),
                ("biomarker", self.biomarkers),
                ("pathway", self.pathways),
            ]:
                for entity in collection.values():
                    data = entity.model_dump()
                    # Convert datetime to ISO string for JSON serialization
                    if isinstance(data.get("created_at"), datetime):
                        data["created_at"] = data["created_at"].isoformat()
                    record = {"type": entity_type, "data": data}
                    f.write(json.dumps(record) + "\n")

    @classmethod
    def load(cls, path: str) -> "EntityCollection":
        """Load from JSONL with type information"""
        collection = cls()

        with open(path, "r") as f:
            for line in f:
                record = json.loads(line)
                entity_type = record["type"]
                data = record["data"]

                if entity_type == "disease":
                    entity = Disease.model_validate(data)
                    collection.diseases[entity.entity_id] = entity
                elif entity_type == "gene":
                    entity = Gene.model_validate(data)
                    collection.genes[entity.entity_id] = entity
                elif entity_type == "drug":
                    entity = Drug.model_validate(data)
                    collection.drugs[entity.entity_id] = entity
                elif entity_type == "protein":
                    entity = Protein.model_validate(data)
                    collection.proteins[entity.entity_id] = entity
                elif entity_type == "symptom":
                    entity = Symptom.model_validate(data)
                    collection.symptoms[entity.entity_id] = entity
                elif entity_type == "procedure":
                    entity = Procedure.model_validate(data)
                    collection.procedures[entity.entity_id] = entity
                elif entity_type == "biomarker":
                    entity = Biomarker.model_validate(data)
                    collection.biomarkers[entity.entity_id] = entity
                elif entity_type == "pathway":
                    entity = Pathway.model_validate(data)
                    collection.pathways[entity.entity_id] = entity

        return collection

    def find_by_embedding(
        self, query_embedding: List[float], top_k: int = 5, threshold: float = 0.85
    ) -> List[Tuple[BaseMedicalEntity, float]]:
        """
        Find entities similar to query embedding.
        Returns list of (entity, similarity_score) tuples.
        """
        from numpy import dot
        from numpy.linalg import norm

        results = []

        for collection in [self.diseases, self.genes, self.drugs, self.proteins]:
            for entity in collection.values():
                if entity.embedding_titan_v2 is None:
                    continue

                # Cosine similarity
                similarity = dot(query_embedding, entity.embedding_titan_v2) / (
                    norm(query_embedding) * norm(entity.embedding_titan_v2)
                )

                if similarity >= threshold:
                    results.append((entity, similarity))

        # Sort by similarity
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]


# =====================


def generate_embeddings_for_entities(
    collection: EntityCollection, batch_size: int = 25
) -> EntityCollection:
    """
    Generate embeddings for all entities across all types.
    Uses AWS Bedrock Titan v2 to create 1024-dim embeddings.
    """

    bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")

    # Collect all entities that need embeddings
    entities_to_process = []
    for collection_dict in [
        collection.diseases,
        collection.genes,
        collection.drugs,
        collection.proteins,
        collection.symptoms,
        collection.procedures,
        collection.biomarkers,
        collection.pathways,
    ]:
        for entity in collection_dict.values():
            if entity.embedding_titan_v2 is None:
                entities_to_process.append(entity)

    print(f"Generating embeddings for {len(entities_to_process)} entities...")

    for i in tqdm(range(0, len(entities_to_process), batch_size)):
        batch = entities_to_process[i : i + batch_size]

        for entity in batch:
            # Combine name, synonyms, and abbreviations for richer embedding
            text = entity.name
            if entity.synonyms:
                text += " " + " ".join(entity.synonyms[:5])
            if entity.abbreviations:
                text += " " + " ".join(entity.abbreviations[:3])

            # Call Bedrock
            response = bedrock.invoke_model(
                modelId="amazon.titan-embed-text-v2:0",
                body=json.dumps(
                    {"inputText": text, "dimensions": 1024, "normalize": True}
                ),
            )

            result = json.loads(response["body"].read())
            entity.embedding_titan_v2 = result["embedding"]

    print(f"✓ Generated embeddings for {len(entities_to_process)} entities")
    return collection
