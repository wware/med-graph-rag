"""
JATS XML Parser for PubMed Central Articles

Extracts structured content from JATS (Journal Article Tag Suite) XML format
for medical research paper ingestion into knowledge graph system.
"""

import xml.etree.ElementTree as ET
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Citation:
    """Represents a citation/reference within the paper"""
    ref_id: str
    cited_pmid: Optional[str] = None
    cited_pmc: Optional[str] = None
    cited_doi: Optional[str] = None
    citation_text: Optional[str] = None


@dataclass
class TableData:
    """Represents a table in the paper"""
    table_id: str
    label: str  # e.g., "Table 1"
    caption: str
    content: str  # We'll store as string; could parse to structured data
    section: str


@dataclass
class Chunk:
    """Represents a chunk of text for embedding"""
    text: str
    section: str
    subsection: Optional[str]
    paragraph_index: int
    chunk_type: str  # 'paragraph', 'sentence', 'abstract'
    citations: List[str] = field(default_factory=list)
    

@dataclass
class PaperMetadata:
    """Core metadata about the paper"""
    pmc_id: str
    pmid: Optional[str]
    doi: Optional[str]
    title: str
    abstract: str
    authors: List[str]
    affiliations: List[str]
    journal: str
    publication_date: Optional[str]
    mesh_terms: List[str]
    keywords: List[str]


@dataclass
class ParsedPaper:
    """Complete parsed paper with all extracted content"""
    metadata: PaperMetadata
    chunks: List[Chunk]
    tables: List[TableData]
    references: Dict[str, Citation]
    full_text: str


class JATSParser:
    """Parser for JATS XML format from PubMed Central"""
    
    # Common JATS XML namespaces
    NAMESPACES = {
        'jats': 'http://jats.nlm.nih.gov',
        'xlink': 'http://www.w3.org/1999/xlink',
        'mml': 'http://www.w3.org/1998/Math/MathML'
    }
    
    def __init__(self, xml_path: str):
        """Initialize parser with path to JATS XML file"""
        self.tree = ET.parse(xml_path)
        self.root = self.tree.getroot()
        
    def parse(self) -> ParsedPaper:
        """Parse the entire JATS XML document"""
        metadata = self._parse_metadata()
        references = self._parse_references()
        chunks = self._parse_body(references)
        tables = self._parse_tables()
        full_text = self._extract_full_text()
        
        return ParsedPaper(
            metadata=metadata,
            chunks=chunks,
            tables=tables,
            references=references,
            full_text=full_text
        )
    
    def _parse_metadata(self) -> PaperMetadata:
        """Extract paper metadata from front matter"""
        front = self.root.find('.//front')
        if front is None:
            raise ValueError("No front matter found in JATS XML")
        
        # Article IDs
        pmc_id = self._get_article_id(front, 'pmc')
        pmid = self._get_article_id(front, 'pmid')
        doi = self._get_article_id(front, 'doi')
        
        # Title
        title = self._get_text(front.find('.//article-title')) or "Unknown Title"
        
        # Abstract
        abstract = self._parse_abstract(front)
        
        # Authors and affiliations
        authors, affiliations = self._parse_authors(front)
        
        # Journal info
        journal = self._get_text(front.find('.//journal-title')) or "Unknown Journal"
        
        # Publication date
        pub_date = self._parse_pub_date(front)
        
        # MeSH terms and keywords
        mesh_terms = self._parse_mesh_terms(front)
        keywords = self._parse_keywords(front)
        
        return PaperMetadata(
            pmc_id=pmc_id,
            pmid=pmid,
            doi=doi,
            title=title,
            abstract=abstract,
            authors=authors,
            affiliations=affiliations,
            journal=journal,
            publication_date=pub_date,
            mesh_terms=mesh_terms,
            keywords=keywords
        )
    
    def _get_article_id(self, front: ET.Element, id_type: str) -> Optional[str]:
        """Extract article ID of specific type"""
        for article_id in front.findall('.//article-id'):
            if article_id.get('pub-id-type') == id_type:
                return article_id.text
        return None
    
    def _parse_abstract(self, front: ET.Element) -> str:
        """Extract and concatenate abstract text"""
        abstract_elem = front.find('.//abstract')
        if abstract_elem is None:
            return ""
        
        # Handle structured abstracts (with sections)
        sections = []
        for sec in abstract_elem.findall('.//sec'):
            title = self._get_text(sec.find('.//title'))
            content = ' '.join(self._get_text(p) for p in sec.findall('.//p'))
            if title:
                sections.append(f"{title}: {content}")
            else:
                sections.append(content)
        
        if sections:
            return ' '.join(sections)
        
        # Handle unstructured abstract
        return ' '.join(self._get_text(p) for p in abstract_elem.findall('.//p'))
    
    def _parse_authors(self, front: ET.Element) -> tuple[List[str], List[str]]:
        """Extract authors and their affiliations"""
        authors = []
        affiliations = []
        
        # Authors
        for contrib in front.findall('.//contrib[@contrib-type="author"]'):
            surname = self._get_text(contrib.find('.//surname'))
            given_names = self._get_text(contrib.find('.//given-names'))
            if surname:
                author = f"{surname} {given_names}" if given_names else surname
                authors.append(author)
        
        # Affiliations
        for aff in front.findall('.//aff'):
            aff_text = self._get_text(aff)
            if aff_text:
                affiliations.append(aff_text)
        
        return authors, affiliations
    
    def _parse_pub_date(self, front: ET.Element) -> Optional[str]:
        """Extract publication date"""
        pub_date = front.find('.//pub-date[@pub-type="epub"]') or \
                   front.find('.//pub-date[@pub-type="ppub"]') or \
                   front.find('.//pub-date')
        
        if pub_date is not None:
            year = self._get_text(pub_date.find('.//year'))
            month = self._get_text(pub_date.find('.//month')) or '01'
            day = self._get_text(pub_date.find('.//day')) or '01'
            
            if year:
                try:
                    return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                except:
                    return year
        return None
    
    def _parse_mesh_terms(self, front: ET.Element) -> List[str]:
        """Extract MeSH (Medical Subject Headings) terms"""
        mesh_terms = []
        for kwd_group in front.findall('.//kwd-group[@kwd-group-type="MeSH"]'):
            for kwd in kwd_group.findall('.//kwd'):
                term = self._get_text(kwd)
                if term:
                    mesh_terms.append(term)
        return mesh_terms
    
    def _parse_keywords(self, front: ET.Element) -> List[str]:
        """Extract author keywords"""
        keywords = []
        for kwd_group in front.findall('.//kwd-group'):
            if kwd_group.get('kwd-group-type') != 'MeSH':
                for kwd in kwd_group.findall('.//kwd'):
                    term = self._get_text(kwd)
                    if term:
                        keywords.append(term)
        return keywords
    
    def _parse_references(self) -> Dict[str, Citation]:
        """Extract all references/citations"""
        references = {}
        back = self.root.find('.//back')
        if back is None:
            return references
        
        for ref in back.findall('.//ref'):
            ref_id = ref.get('id')
            if not ref_id:
                continue
            
            # Try to extract PMIDs, PMC IDs, DOIs
            pmid = None
            pmc = None
            doi = None
            
            for pub_id in ref.findall('.//pub-id'):
                pub_id_type = pub_id.get('pub-id-type')
                if pub_id_type == 'pmid':
                    pmid = pub_id.text
                elif pub_id_type == 'pmc':
                    pmc = pub_id.text
                elif pub_id_type == 'doi':
                    doi = pub_id.text
            
            # Get citation text
            citation_text = self._get_text(ref)
            
            references[ref_id] = Citation(
                ref_id=ref_id,
                cited_pmid=pmid,
                cited_pmc=pmc,
                cited_doi=doi,
                citation_text=citation_text
            )
        
        return references
    
    def _parse_body(self, references: Dict[str, Citation]) -> List[Chunk]:
        """Parse the main body of the paper into chunks"""
        chunks = []
        body = self.root.find('.//body')
        if body is None:
            return chunks
        
        # Add abstract as first chunk
        front = self.root.find('.//front')
        if front is not None:
            abstract_text = self._parse_abstract(front)
            if abstract_text:
                chunks.append(Chunk(
                    text=abstract_text,
                    section='abstract',
                    subsection=None,
                    paragraph_index=0,
                    chunk_type='abstract',
                    citations=[]
                ))
        
        # Process each section
        for sec in body.findall('.//sec'):
            section_name = self._get_text(sec.find('.//title')) or 'unknown'
            section_name = section_name.lower().replace(' ', '_')
            
            # Process subsections recursively
            chunks.extend(self._parse_section(sec, section_name, references))
        
        return chunks
    
    def _parse_section(self, sec: ET.Element, parent_section: str, 
                       references: Dict[str, Citation], 
                       paragraph_counter: int = 0) -> List[Chunk]:
        """Recursively parse a section and its subsections"""
        chunks = []
        
        # Get section title (for subsections)
        title = self._get_text(sec.find('./title'))
        subsection = title.lower().replace(' ', '_') if title else None
        
        # Process paragraphs in this section
        for p in sec.findall('./p'):
            paragraph_text = self._get_paragraph_text(p)
            if not paragraph_text.strip():
                continue
            
            # Extract citation references in this paragraph
            citation_ids = [xref.get('rid') for xref in p.findall('.//xref[@ref-type="bibr"]')
                          if xref.get('rid') in references]
            
            chunks.append(Chunk(
                text=paragraph_text,
                section=parent_section,
                subsection=subsection,
                paragraph_index=paragraph_counter,
                chunk_type='paragraph',
                citations=citation_ids
            ))
            paragraph_counter += 1
        
        # Recursively process nested sections
        for nested_sec in sec.findall('./sec'):
            nested_title = self._get_text(nested_sec.find('./title')) or 'subsection'
            nested_name = f"{parent_section}.{nested_title.lower().replace(' ', '_')}"
            chunks.extend(self._parse_section(nested_sec, nested_name, references, paragraph_counter))
            paragraph_counter += len(chunks)
        
        return chunks
    
    def _parse_tables(self) -> List[TableData]:
        """Extract tables with their captions"""
        tables = []
        
        for table_wrap in self.root.findall('.//table-wrap'):
            table_id = table_wrap.get('id', 'unknown')
            
            # Get label (e.g., "Table 1")
            label = self._get_text(table_wrap.find('.//label')) or table_id
            
            # Get caption
            caption = self._get_text(table_wrap.find('.//caption')) or ""
            
            # Get table content (simplified - just text representation)
            table_elem = table_wrap.find('.//table')
            content = self._get_text(table_elem) if table_elem is not None else ""
            
            # Try to determine which section this table belongs to
            section = self._find_table_section(table_wrap)
            
            tables.append(TableData(
                table_id=table_id,
                label=label,
                caption=caption,
                content=content,
                section=section
            ))
        
        return tables
    
    def _find_table_section(self, table_wrap: ET.Element) -> str:
        """Find which section a table belongs to"""
        # Walk up the tree to find the containing section
        parent = table_wrap
        while parent is not None:
            if parent.tag == 'sec':
                title = self._get_text(parent.find('./title'))
                return title.lower().replace(' ', '_') if title else 'unknown'
            parent = parent.getparent() if hasattr(parent, 'getparent') else None
        return 'unknown'
    
    def _extract_full_text(self) -> str:
        """Extract complete plain text of the paper"""
        text_parts = []
        
        # Add abstract
        front = self.root.find('.//front')
        if front is not None:
            abstract = self._parse_abstract(front)
            if abstract:
                text_parts.append(abstract)
        
        # Add body text
        body = self.root.find('.//body')
        if body is not None:
            body_text = self._get_text(body)
            if body_text:
                text_parts.append(body_text)
        
        return '\n\n'.join(text_parts)
    
    def _get_paragraph_text(self, elem: ET.Element) -> str:
        """Extract text from paragraph, handling inline elements"""
        if elem is None:
            return ""
        
        # Get text including all nested elements
        text_parts = [elem.text or ""]
        
        for child in elem:
            # Skip certain elements
            if child.tag in ['xref', 'sup', 'sub']:
                text_parts.append(child.text or "")
            else:
                text_parts.append(self._get_text(child))
            
            # Add tail text
            text_parts.append(child.tail or "")
        
        return ' '.join(text_parts).strip()
    
    def _get_text(self, elem: Optional[ET.Element]) -> str:
        """Recursively extract all text from an element"""
        if elem is None:
            return ""
        
        text_parts = []
        
        # Get direct text
        if elem.text:
            text_parts.append(elem.text)
        
        # Get text from children
        for child in elem:
            text_parts.append(self._get_text(child))
            if child.tail:
                text_parts.append(child.tail)
        
        return ' '.join(text_parts).strip()


def example_usage():
    """Example of how to use the parser"""
    
    # Parse a JATS XML file
    parser = JATSParser('path/to/paper.xml')
    paper = parser.parse()
    
    # Access metadata
    print(f"Title: {paper.metadata.title}")
    print(f"PMC ID: {paper.metadata.pmc_id}")
    print(f"PMID: {paper.metadata.pmid}")
    print(f"Authors: {', '.join(paper.metadata.authors)}")
    print(f"Publication Date: {paper.metadata.publication_date}")
    print(f"MeSH Terms: {', '.join(paper.metadata.mesh_terms)}")
    
    # Access chunks for embedding
    print(f"\nTotal chunks: {len(paper.chunks)}")
    for i, chunk in enumerate(paper.chunks[:3]):
        print(f"\nChunk {i+1}:")
        print(f"  Section: {chunk.section}")
        print(f"  Type: {chunk.chunk_type}")
        print(f"  Text preview: {chunk.text[:100]}...")
        print(f"  Citations: {chunk.citations}")
    
    # Access tables
    print(f"\nTotal tables: {len(paper.tables)}")
    for table in paper.tables:
        print(f"\n{table.label}: {table.caption}")
    
    # Access references
    print(f"\nTotal references: {len(paper.references)}")


if __name__ == '__main__':
    example_usage()
