def load_umls_subset() -> EntityCollection:
    """
    Load UMLS concepts (requires UMLS license)
    
    UMLS Metathesaurus download: https://www.nlm.nih.gov/research/umls/
    
    Key files from UMLS:
    - MRCONSO.RRF: Concept names and synonyms
    - MRSTY.RRF: Semantic types
    """
    
    entities = {}
    entity_counter = 1
    
    # Load semantic types (disease, drug, etc.)
    umls_types = {}  # CUI -> semantic type
    with open('UMLS/MRSTY.RRF', 'r', encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split('|')
            cui = parts[0]
            semantic_type = parts[3]
            umls_types[cui] = semantic_type
    
    # Load concept names and synonyms
    concept_names = {}  # CUI -> (preferred_name, [synonyms])
    with open('UMLS/MRCONSO.RRF', 'r', encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split('|')
            cui = parts[0]
            language = parts[1]
            
            # Only English
            if language != 'ENG':
                continue
            
            term = parts[14]
            is_preferred = parts[6] == 'P'  # Preferred term
            
            if cui not in concept_names:
                concept_names[cui] = (term if is_preferred else None, [])
            
            if is_preferred:
                concept_names[cui] = (term, concept_names[cui][1])
            else:
                concept_names[cui][1].append(term)
    
    # Create entities
    for cui, (preferred_name, synonyms) in concept_names.items():
        if not preferred_name:
            continue
        
        # Get semantic type
        semantic_type = umls_types.get(cui, 'concept')
        entity_type = map_umls_semantic_type(semantic_type)
        
        # Filter to medical concepts only
        if entity_type not in ['disease', 'drug', 'gene', 'protein', 'symptom']:
            continue
        
        entity = ReferenceEntity(
            entity_id=f"ENTITY:{entity_counter:06d}",
            canonical_name=preferred_name,
            entity_type=entity_type,
            umls_id=cui,
            synonyms=synonyms[:20],  # Limit synonyms
            source="umls",
            created_at=datetime.now()
        )
        
        entities[entity.entity_id] = entity
        entity_counter += 1
    
    return EntityCollection(
        entities=entities,
        entity_count=len(entities),
        version="umls_2024"
    )


def map_umls_semantic_type(semantic_type: str) -> str:
    """Map UMLS semantic types to our simplified types"""
    mapping = {
        'Disease or Syndrome': 'disease',
        'Neoplastic Process': 'disease',
        'Pharmacologic Substance': 'drug',
        'Antibiotic': 'drug',
        'Gene or Genome': 'gene',
        'Amino Acid, Peptide, or Protein': 'protein',
        'Sign or Symptom': 'symptom',
        'Clinical Attribute': 'biomarker',
    }
    return mapping.get(semantic_type, 'concept')
