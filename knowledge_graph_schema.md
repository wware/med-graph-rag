# Medical Research Knowledge Graph Schema

## Overview

This schema is designed to support clinical decision-making by representing medical knowledge extracted from research papers. The graph enables multi-hop reasoning, contradiction detection, and evidence-based inference.

## Design Principles

1. **Clinical utility first** - Schema supports queries doctors actually ask
2. **Provenance always** - Every relationship traces back to source papers
3. **Handle uncertainty** - Represent confidence, contradictions, and evolution over time
4. **Standards-based** - Use UMLS, MeSH, and other medical ontologies for entity IDs
5. **Scalable** - Can grow from thousands to millions of papers

## Node Types

### Common Entity Properties

All medical entities (Disease, Gene, Drug, Protein, etc.) share these base properties:

```
- entity_id: Unique identifier (type-specific, e.g., UMLS ID, HGNC ID)
- name: Primary canonical name
- synonyms: [list of alternate names]
- abbreviations: [common abbreviations, e.g., "T2DM", "NIDDM"]
- embedding_titan_v2: Pre-computed 1024-dim embedding for semantic search
- embedding_pubmedbert: Pre-computed 768-dim biomedical embedding
- created_at: Timestamp when entity was added
- source: Origin ("umls", "mesh", "rxnorm", "hgnc", "uniprot", "extracted")
```

### Core Medical Entities

#### Disease
Represents medical conditions, disorders, syndromes
```
Properties:
- entity_id: UMLS Concept ID (e.g., C0006142 for "Breast Cancer")
- name: Primary name
- synonyms: [list of alternate names]
- abbreviations: [common abbreviations]
- umls_id: UMLS Concept ID (same as entity_id)
- mesh_id: Medical Subject Heading ID
- icd10_codes: [list of ICD-10 codes]
- category: (genetic, infectious, autoimmune, etc.)
- [plus common entity properties above]
```

#### Gene
Represents genes and genetic variants
```
Properties:
- entity_id: HGNC ID (e.g., HGNC:1100 for BRCA1)
- symbol: Gene symbol (BRCA1)
- name: Full name
- synonyms: [alternate symbols]
- hgnc_id: HGNC identifier (same as entity_id)
- chromosome: Location (17q21.31)
- entrez_id: NCBI Gene ID
- [plus common entity properties above]
```

#### Mutation
Represents specific genetic variants
```
Properties:
- id: dbSNP ID or HGVS notation (e.g., rs80357906)
- gene_id: Parent gene
- variant_type: (SNP, deletion, insertion, etc.)
- notation: HGVS string (c.68_69delAG)
- consequence: (missense, nonsense, frameshift, etc.)
```

#### Drug
Represents medications and therapeutic substances
```
Properties:
- entity_id: RxNorm Concept ID
- name: Generic name
- synonyms: [alternate names]
- rxnorm_id: RxNorm identifier (same as entity_id)
- brand_names: [list of brand names]
- drug_class: (chemotherapy, immunotherapy, etc.)
- mechanism: Mechanism of action
- [plus common entity properties above]
```

#### Protein
Represents proteins and their functions
```
Properties:
- entity_id: UniProt ID
- name: Protein name
- synonyms: [alternate names]
- uniprot_id: UniProt accession (same as entity_id)
- gene_id: Encoding gene
- function: Biological function
- pathways: [biological pathways involved in]
- [plus common entity properties above]
```

#### Symptom
Represents clinical signs and symptoms
```
Properties:
- id: UMLS Concept ID
- name: Symptom name
- synonyms: [alternate descriptions]
- severity_scale: (mild, moderate, severe, etc.)
```

#### Procedure
Represents medical tests, diagnostics, treatments
```
Properties:
- id: CPT code or UMLS ID
- name: Procedure name
- type: (diagnostic, therapeutic, preventive)
- invasiveness: (non-invasive, minimally invasive, invasive)
```

#### Biomarker
Represents measurable indicators
```
Properties:
- entity_id: LOINC code or UMLS ID
- name: Biomarker name
- synonyms: [alternate descriptions]
- loinc_code: LOINC code for standardized lab tests
- measurement_type: (blood, tissue, imaging)
- normal_range: Reference values
- [plus common entity properties above]
```

#### Pathway
Represents biological pathways
```
Properties:
- entity_id: KEGG or Reactome ID
- name: Pathway name
- synonyms: [alternate names]
- kegg_id: KEGG pathway identifier
- reactome_id: Reactome pathway identifier
- category: (signaling, metabolic, etc.)
- genes_involved: [list of gene IDs]
- [plus common entity properties above]
```

### Research Metadata Nodes

#### Paper
Represents a research paper
```
Properties:
- pmc_id: PubMed Central ID
- pmid: PubMed ID
- doi: Digital Object Identifier
- title: Paper title
- abstract: Full abstract
- authors: [list of authors]
- journal: Journal name
- publication_date: Date published
- study_type: (RCT, cohort, case-control, review, meta-analysis)
- sample_size: Number of subjects
- mesh_terms: [Medical Subject Headings]
```

#### Author
Represents researchers
```
Properties:
- orcid: ORCID identifier
- name: Full name
- affiliations: [institutions]
- h_index: Citation metric
```

#### ClinicalTrial
Represents clinical trials
```
Properties:
- nct_id: ClinicalTrials.gov identifier
- title: Trial title
- phase: (I, II, III, IV)
- status: (recruiting, completed, etc.)
- intervention: Treatment being tested
```

## Edge Types (Relationships)

### Medical Relationships

#### CAUSES
`Disease -[CAUSES]-> Symptom`
```
Properties:
- frequency: How often (always, often, sometimes, rarely)
- onset: When it appears (early, late)
- severity: Typical severity
- source_papers: [PMC IDs]
- confidence: 0.0-1.0 (based on evidence strength)
- contradicted_by: [PMC IDs of contradicting papers]
```

#### TREATS
`Drug -[TREATS]-> Disease`
```
Properties:
- efficacy: Effectiveness measure
- response_rate: Percentage of patients responding
- line_of_therapy: (first-line, second-line, etc.)
- indication: Specific approved use
- source_papers: [PMC IDs]
- confidence: 0.0-1.0
- contradicted_by: [PMC IDs]
```

#### INCREASES_RISK
`Gene/Mutation -[INCREASES_RISK]-> Disease`
```
Properties:
- risk_ratio: Numeric risk increase (e.g., 2.5x)
- penetrance: Percentage who develop condition
- age_of_onset: Typical age
- population: Studied population
- source_papers: [PMC IDs]
- confidence: 0.0-1.0
```

#### ASSOCIATED_WITH
Generic association between entities
```
Disease -[ASSOCIATED_WITH]-> Disease
Gene -[ASSOCIATED_WITH]-> Disease
Biomarker -[ASSOCIATED_WITH]-> Disease

Properties:
- association_type: (positive, negative, neutral)
- strength: (strong, moderate, weak)
- statistical_significance: p-value
- source_papers: [PMC IDs]
- confidence: 0.0-1.0
- contradicted_by: [PMC IDs]
```

#### INTERACTS_WITH
`Drug -[INTERACTS_WITH]-> Drug`
```
Properties:
- interaction_type: (synergistic, antagonistic, additive)
- severity: (major, moderate, minor)
- mechanism: How they interact
- clinical_significance: Description
- source_papers: [PMC IDs]
```

#### ENCODES
`Gene -[ENCODES]-> Protein`
```
Properties:
- transcript_variants: Number of variants
- tissue_specificity: Where expressed
- source_papers: [PMC IDs]
```

#### PARTICIPATES_IN
`Gene/Protein -[PARTICIPATES_IN]-> Pathway`
```
Properties:
- role: Function in pathway
- regulatory_effect: (activates, inhibits, modulates)
- source_papers: [PMC IDs]
```

#### CONTRAINDICATED_FOR
`Drug -[CONTRAINDICATED_FOR]-> Disease/Condition`
```
Properties:
- severity: (absolute, relative)
- reason: Why contraindicated
- source_papers: [PMC IDs]
```

#### DIAGNOSED_BY
`Disease -[DIAGNOSED_BY]-> Procedure/Biomarker`
```
Properties:
- sensitivity: True positive rate
- specificity: True negative rate
- standard_of_care: Boolean
- source_papers: [PMC IDs]
```

#### SIDE_EFFECT
`Drug -[SIDE_EFFECT]-> Symptom`
```
Properties:
- frequency: (common, uncommon, rare)
- severity: (mild, moderate, severe)
- reversible: Boolean
- source_papers: [PMC IDs]
```

### Research Metadata Relationships

#### CITES
`Paper -[CITES]-> Paper`
```
Properties:
- context: What section the citation appears in
- sentiment: (supports, contradicts, mentions)
```

#### STUDIED_IN
`(Any medical entity) -[STUDIED_IN]-> Paper`
```
Properties:
- role: (primary_focus, secondary_finding, mentioned)
- section: Where discussed (results, methods, discussion)
```

#### AUTHORED_BY
`Paper -[AUTHORED_BY]-> Author`
```
Properties:
- position: (first, last, corresponding, middle)
```

#### PART_OF
`Paper -[PART_OF]-> ClinicalTrial`
```
Properties:
- publication_type: (protocol, results, analysis)
```

## Provenance and Evidence

Every medical relationship edge MUST include:

```
- source_papers: [list of PMC IDs supporting this relationship]
- evidence_count: Number of papers supporting
- contradicted_by: [list of PMC IDs contradicting]
- first_reported: Date first observed
- last_updated: Most recent evidence
- confidence: Calculated from evidence strength (0.0-1.0)
```

## Confidence Scoring

Confidence for each relationship calculated from:

1. **Number of supporting papers** - More evidence = higher confidence
2. **Study quality** - RCTs weighted higher than case reports
3. **Sample size** - Larger studies weighted higher
4. **Recency** - More recent papers weighted slightly higher
5. **Contradictions** - Presence reduces confidence
6. **Journal impact** - Higher impact journals weighted slightly higher

Formula:
```
confidence = base_score * quality_multiplier * (1 - contradiction_penalty)

where:
- base_score = min(evidence_count / 10, 0.8)  # Caps at 0.8 with 10+ papers
- quality_multiplier = weighted average of study types
- contradiction_penalty = contradicting_count / (evidence_count + contradicting_count)
```

## Handling Contradictions

When papers disagree:

1. **Preserve both relationships** - Don't delete contradicting evidence
2. **Link contradictions** - Add `contradicted_by` property
3. **Surface in queries** - Show users when evidence conflicts
4. **Track evolution** - Understanding may change over time

Example:
```
Drug A -[TREATS]-> Disease X
  source_papers: [PMC111, PMC222, PMC333]
  confidence: 0.75
  contradicted_by: [PMC444]  # One paper found no effect
```

## Temporal Representation

Medical knowledge evolves. Track this with:

```
Drug -[TREATS {valid_from: "2015", valid_to: "2020"}]-> Disease
  # Was considered treatment from 2015-2020

Drug -[TREATS {valid_from: "2020", valid_to: null}]-> Disease
  # New understanding starting 2020
```

## Example Graph Snippet

```
(:Gene {id: "HGNC:1100", symbol: "BRCA1"})
  -[:ENCODES]->
(:Protein {id: "P38398", name: "Breast cancer type 1 susceptibility protein"})

(:Gene {id: "HGNC:1100"})
  -[:INCREASES_RISK {
      risk_ratio: 5.0,
      penetrance: 0.72,
      source_papers: ["PMC123", "PMC456", "PMC789"],
      confidence: 0.92
    }]->
(:Disease {id: "C0006142", name: "Breast Cancer"})

(:Mutation {id: "rs80357906", variant: "c.68_69delAG"})
  -[:VARIANT_OF]->
(:Gene {id: "HGNC:1100"})

(:Drug {id: "RxNorm:1187832", name: "Olaparib"})
  -[:TREATS {
      indication: "BRCA-mutated breast cancer",
      response_rate: 0.59,
      source_papers: ["PMC999", "PMC888"],
      confidence: 0.85
    }]->
(:Disease {id: "C0006142"})

(:Paper {pmc_id: "PMC999"})
  -[:STUDIED_IN]->
(:Drug {id: "RxNorm:1187832"})
```

## Query Examples This Schema Enables

1. **"What treats breast cancer?"**
   ```
   MATCH (d:Drug)-[t:TREATS]->(disease:Disease {name: "Breast Cancer"})
   RETURN d.name, t.efficacy, t.source_papers
   ORDER BY t.confidence DESC
   ```

2. **"What are the risks associated with BRCA1 mutations?"**
   ```
   MATCH (g:Gene {symbol: "BRCA1"})-[r:INCREASES_RISK]->(d:Disease)
   RETURN d.name, r.risk_ratio, r.source_papers
   ORDER BY r.risk_ratio DESC
   ```

3. **"Are there contradictions about Drug X efficacy?"**
   ```
   MATCH (drug:Drug {name: "X"})-[t:TREATS]->(d:Disease)
   WHERE size(t.contradicted_by) > 0
   RETURN d.name, t.source_papers, t.contradicted_by
   ```

4. **"What pathways is BRCA1 involved in?"**
   ```
   MATCH (g:Gene {symbol: "BRCA1"})-[:ENCODES]->(p:Protein)
         -[:PARTICIPATES_IN]->(path:Pathway)
   RETURN path.name, path.category
   ```

## Implementation Notes

### Graph Database Choice

**Option 1: Amazon Neptune**
- Pros: AWS native, fully managed, supports Gremlin/SPARQL
- Cons: More expensive, separate service from OpenSearch

**Option 2: Neo4j**
- Pros: Mature, excellent Cypher query language, strong community
- Cons: Need to manage separately, extra infrastructure

**Option 3: OpenSearch with graph queries**
- Pros: Already using OpenSearch, fewer moving parts
- Cons: Graph capabilities less mature than dedicated graph DBs

**Recommendation:** Start with Neo4j for development (can run locally), migrate to Neptune for production if needed.

### Entity Normalization Strategy

1. **Primary entities** (Disease, Gene, Drug) get canonical IDs from:
   - UMLS (diseases, symptoms, general medical concepts)
   - HGNC (genes)
   - RxNorm (drugs)
   - UniProt (proteins)

2. **Entity linking pipeline:**
   ```
   Extracted text → NER → Candidate entities →
   Entity linking → Canonical ID → Graph node
   ```

3. **Handle synonyms:**
   - Store all variants in `synonyms` property
   - Create index on synonyms for fast lookup
   - Map during extraction phase

### Incremental Building

1. **Start simple** - Just diseases, genes, drugs, basic relationships
2. **Add complexity** - Proteins, pathways, biomarkers
3. **Add metadata** - Authors, trials, more detailed provenance
4. **Refine confidence** - Better scoring as you learn what works

## Implementation Notes

### Entity Architecture

The implementation uses **strongly-typed entity classes** (Disease, Gene, Drug, Protein, etc.) as the canonical representation for all entities. Each typed entity includes:

- **Type-specific ID fields** (e.g., `umls_id` for Disease, `hgnc_id` for Gene)
- **Pre-computed embeddings** (Titan v2, PubMedBERT) for semantic search
- **Provenance metadata** (`source`, `created_at`) for tracking entity origins

This approach provides better type safety and validation compared to a generic entity class.

### Entity Collection Storage

Entities are stored in an `EntityCollection` organized by type:
- `diseases: Dict[str, Disease]`
- `genes: Dict[str, Gene]`
- `drugs: Dict[str, Drug]`
- `proteins: Dict[str, Protein]`
- Plus: symptoms, procedures, biomarkers, pathways

Persistence format (JSONL):
```json
{"type": "disease", "data": {...}}
{"type": "gene", "data": {...}}
```

### Relationship Provenance

All medical relationships inherit from `BaseMedicalRelationship` which includes:
- `source_papers`: List of PMC IDs
- `confidence`: Float (0.0-1.0)
- `evidence_count`: Integer
- `contradicted_by`: List of PMC IDs
- `first_reported`: Date string
- `last_updated`: Date string

Research metadata relationships (`Cites`, `StudiedIn`, `AuthoredBy`, `PartOf`) use a simpler `ResearchRelationship` base class without provenance tracking since they represent bibliographic metadata rather than medical claims.
