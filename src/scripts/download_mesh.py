import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

def download_mesh() -> EntityCollection:
    """
    Download MeSH descriptors and convert to ReferenceEntity format
    
    MeSH XML format: https://www.nlm.nih.gov/databases/download/mesh.html
    """
    
    # Download MeSH XML (annual release, ~300MB)
    mesh_url = "https://nlmpubs.nlm.nih.gov/projects/mesh/MESH_FILES/xmlmesh/desc2024.xml"
    
    print("Downloading MeSH descriptors...")
    with urllib.request.urlopen(mesh_url) as response:
        mesh_xml = response.read()
    
    # Parse XML
    root = ET.fromstring(mesh_xml)
    
    entities = {}
    entity_counter = 1
    
    for descriptor in root.findall('.//DescriptorRecord'):
        # Get MeSH ID
        mesh_id = descriptor.find('.//DescriptorUI').text
        
        # Get canonical name
        name = descriptor.find('.//DescriptorName/String').text
        
        # Get synonyms (ConceptList)
        synonyms = []
        for term in descriptor.findall('.//Term/String'):
            syn = term.text
            if syn != name:
                synonyms.append(syn)
        
        # Determine entity type from tree numbers
        tree_numbers = [
            tn.text for tn in descriptor.findall('.//TreeNumber')
        ]
        entity_type = classify_mesh_type(tree_numbers)
        
        # Create entity
        entity = ReferenceEntity(
            entity_id=f"ENTITY:{entity_counter:06d}",
            canonical_name=name,
            entity_type=entity_type,
            mesh_id=mesh_id,
            synonyms=synonyms,
            source="mesh",
            created_at=datetime.now()
        )
        
        entities[entity.entity_id] = entity
        entity_counter += 1
    
    return EntityCollection(
        entities=entities,
        entity_count=len(entities),
        version="mesh_2024"
    )


def classify_mesh_type(tree_numbers: List[str]) -> str:
    """
    Classify MeSH term based on tree number
    
    Tree categories:
    - C: Diseases
    - D: Chemicals and Drugs
    - G: Phenomena and Processes
    - etc.
    """
    if not tree_numbers:
        return "concept"
    
    first_letter = tree_numbers[0][0]
    
    mapping = {
        'C': 'disease',
        'D': 'drug',
        'G': 'biological_process',
        'A': 'anatomy',
        'F': 'psychiatry_psychology',
    }
    
    return mapping.get(first_letter, 'concept')
