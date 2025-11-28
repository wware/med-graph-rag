"""
PubMed Central Fetcher

Downloads JATS XML files from PubMed Central Open Access subset using the NCBI E-utilities API.
Supports searching by keywords, filtering by date/journal, and bulk downloading.
"""

import requests
import time
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional, Set, Any, Union
from pydantic import BaseModel
from pathlib import Path
import json
from urllib.parse import urlencode


class PaperMetadata(BaseModel):
    """Minimal metadata for a paper from search results.

    Attributes:
        pmc_id (str): PubMed Central ID.
        pmid (Optional[str]): PubMed ID.
        title (str): Paper title.
        authors (List[str]): List of authors.
        journal (str): Journal name.
        pub_date (str): Publication date.
        doi (Optional[str]): DOI.
    """
    pmc_id: str
    pmid: Optional[str]
    title: str
    authors: List[str]
    journal: str
    pub_date: str
    doi: Optional[str] = None


class PubMedCentralFetcher:
    """Fetch papers from PubMed Central Open Access subset.

    Uses NCBI E-utilities API:
    - ESearch: Search for papers
    - EFetch: Download full JATS XML
    - ESummary: Get metadata

    Attributes:
        email (str): User email (required by NCBI).
        api_key (Optional[str]): NCBI API key.
        tool (str): Name of the tool.
        rate_limit (float): Seconds between requests.
        last_request_time (float): Timestamp of the last request.
    """

    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    PMC_OA_FTP = "https://ftp.ncbi.nlm.nih.gov/pub/pmc"

    def __init__(self,
                 email: str,
                 api_key: Optional[str] = None,
                 tool: str = "medical_knowledge_graph",
                 rate_limit: float = 0.34):
        """Initialize the fetcher.

        Args:
            email (str): Your email (required by NCBI).
            api_key (Optional[str]): NCBI API key (optional, increases rate limit to 10/sec).
            tool (str): Name of your tool (for NCBI logging). Defaults to "medical_knowledge_graph".
            rate_limit (float): Seconds between requests (0.34 = ~3/sec without key, 0.1 = 10/sec with key).
                Defaults to 0.34.
        """
        self.email = email
        self.api_key = api_key
        self.tool = tool
        self.rate_limit = rate_limit if not api_key else 0.1
        self.last_request_time = 0

    def _rate_limit_wait(self) -> None:
        """Enforce rate limiting between API calls."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self.last_request_time = time.time()

    def _make_request(self, endpoint: str, params: Dict[str, Any]) -> requests.Response:
        """Make a rate-limited request to NCBI E-utilities.

        Args:
            endpoint (str): The API endpoint to call.
            params (Dict[str, Any]): The query parameters.

        Returns:
            requests.Response: The API response.

        Raises:
            requests.exceptions.RequestException: If the request fails.
        """
        self._rate_limit_wait()

        # Add required parameters
        params['email'] = self.email
        params['tool'] = self.tool
        if self.api_key:
            params['api_key'] = self.api_key

        url = f"{self.BASE_URL}/{endpoint}"

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            print(f"Error making request to {endpoint}: {e}")
            raise

    def search_papers(self,
                     query: str,
                     max_results: int = 100,
                     start_date: Optional[str] = None,
                     end_date: Optional[str] = None,
                     sort: str = "relevance") -> List[str]:
        """Search PubMed Central for papers matching query.

        Args:
            query (str): Search query (e.g., "breast cancer BRCA1").
            max_results (int): Maximum number of results to return. Defaults to 100.
            start_date (Optional[str]): Filter by publication date (YYYY/MM/DD format).
            end_date (Optional[str]): Filter by publication date (YYYY/MM/DD format).
            sort (str): Sort order ("relevance" or "pub_date"). Defaults to "relevance".

        Returns:
            List[str]: List of PMC IDs (without "PMC" prefix).
        """
        # Build the query
        search_query = f"{query} AND open access[filter]"  # Only open access papers

        if start_date or end_date:
            date_range = f"{start_date or '1900'}:{end_date or '3000'}"
            search_query += f" AND {date_range}[pdat]"

        params = {
            'db': 'pmc',
            'term': search_query,
            'retmax': max_results,
            'retmode': 'json',
            'sort': sort
        }

        print(f"Searching PMC: {search_query}")
        response = self._make_request('esearch.fcgi', params)

        data = response.json()
        id_list = data.get('esearchresult', {}).get('idlist', [])

        print(f"Found {len(id_list)} papers")
        return id_list

    def get_paper_metadata(self, pmc_ids: List[str]) -> List[PaperMetadata]:
        """Get metadata for papers (useful for filtering before downloading).

        Args:
            pmc_ids (List[str]): List of PMC IDs (without "PMC" prefix).

        Returns:
            List[PaperMetadata]: List of PaperMetadata objects.
        """
        if not pmc_ids:
            return []

        # ESummary can handle up to 500 IDs at once
        batch_size = 500
        all_metadata = []

        for i in range(0, len(pmc_ids), batch_size):
            batch = pmc_ids[i:i + batch_size]

            params = {
                'db': 'pmc',
                'id': ','.join(batch),
                'retmode': 'json'
            }

            response = self._make_request('esummary.fcgi', params)
            data = response.json()

            result = data.get('result', {})

            for pmc_id in batch:
                if pmc_id not in result:
                    continue

                paper_data = result[pmc_id]

                # Extract authors
                authors = []
                for author in paper_data.get('authors', []):
                    name = author.get('name', '')
                    if name:
                        authors.append(name)

                metadata = PaperMetadata(
                    pmc_id=pmc_id,
                    pmid=paper_data.get('uid'),  # Sometimes this is PMID
                    title=paper_data.get('title', ''),
                    authors=authors,
                    journal=paper_data.get('fulljournalname', ''),
                    pub_date=paper_data.get('pubdate', ''),
                    doi=paper_data.get('elocationid', '')  # Sometimes this is DOI
                )

                all_metadata.append(metadata)

            print(f"Retrieved metadata for {len(all_metadata)}/{len(pmc_ids)} papers")

        return all_metadata

    def download_paper_xml(self, pmc_id: str, output_dir: Path) -> Optional[Path]:
        """Download JATS XML for a single paper.

        Args:
            pmc_id (str): PMC ID (without "PMC" prefix).
            output_dir (Path): Directory to save XML files.

        Returns:
            Optional[Path]: Path to downloaded file, or None if failed.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / f"PMC{pmc_id}.xml"

        # Check if already downloaded
        if output_file.exists():
            print(f"PMC{pmc_id} already exists, skipping")
            return output_file

        # Use EFetch to get the full XML
        params = {
            'db': 'pmc',
            'id': pmc_id,
            'retmode': 'xml'
        }

        try:
            response = self._make_request('efetch.fcgi', params)

            # Parse to verify it's valid XML
            try:
                ET.fromstring(response.content)
            except ET.ParseError as e:
                print(f"Invalid XML for PMC{pmc_id}: {e}")
                return None

            # Save to file
            with open(output_file, 'wb') as f:
                f.write(response.content)

            print(f"Downloaded PMC{pmc_id}")
            return output_file

        except Exception as e:
            print(f"Error downloading PMC{pmc_id}: {e}")
            return None

    def download_papers_batch(self,
                              pmc_ids: List[str],
                              output_dir: Path,
                              save_metadata: bool = True) -> Dict[str, int]:
        """Download multiple papers.

        Args:
            pmc_ids (List[str]): List of PMC IDs.
            output_dir (Path): Directory to save files.
            save_metadata (bool): Whether to save a metadata JSON file. Defaults to True.

        Returns:
            Dict[str, int]: Dict with success/failure counts.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        success = 0
        failed = 0
        downloaded_files = []

        # Get metadata first if requested
        if save_metadata:
            print("Fetching metadata for all papers...")
            metadata_list = self.get_paper_metadata(pmc_ids)
            metadata_file = output_dir / "papers_metadata.json"

            with open(metadata_file, 'w') as f:
                json.dump([
                    {
                        'pmc_id': m.pmc_id,
                        'pmid': m.pmid,
                        'title': m.title,
                        'authors': m.authors,
                        'journal': m.journal,
                        'pub_date': m.pub_date,
                        'doi': m.doi
                    } for m in metadata_list
                ], f, indent=2)

            print(f"Saved metadata to {metadata_file}")

        # Download each paper
        for i, pmc_id in enumerate(pmc_ids):
            print(f"\nDownloading {i+1}/{len(pmc_ids)}: PMC{pmc_id}")

            result = self.download_paper_xml(pmc_id, output_dir)

            if result:
                success += 1
                downloaded_files.append(result)
            else:
                failed += 1

            # Progress update every 50 papers
            if (i + 1) % 50 == 0:
                print(f"Progress: {success} successful, {failed} failed")

        # Save list of downloaded files
        files_list = output_dir / "downloaded_files.txt"
        with open(files_list, 'w') as f:
            for file_path in downloaded_files:
                f.write(f"{file_path}\n")

        return {
            "success": success,
            "failed": failed,
            "total": len(pmc_ids)
        }

    def search_and_download(self,
                           query: str,
                           output_dir: Path,
                           max_results: int = 100,
                           start_date: Optional[str] = None,
                           end_date: Optional[str] = None) -> Dict[str, int]:
        """Search for papers and download them in one operation.

        Args:
            query (str): Search query.
            output_dir (Path): Directory to save files.
            max_results (int): Maximum number of papers to download. Defaults to 100.
            start_date (Optional[str]): Filter by publication date (YYYY/MM/DD).
            end_date (Optional[str]): Filter by publication date (YYYY/MM/DD).

        Returns:
            Dict[str, int]: Dict with success/failure counts.
        """
        # Search
        pmc_ids = self.search_papers(
            query=query,
            max_results=max_results,
            start_date=start_date,
            end_date=end_date
        )

        if not pmc_ids:
            print("No papers found")
            return {"success": 0, "failed": 0, "total": 0}

        # Download
        return self.download_papers_batch(pmc_ids, output_dir)


class PMCBulkDownloader:
    """Alternative approach: Download from PMC Open Access bulk files.

    PMC provides bulk downloads organized by journal. This is much faster
    for large-scale downloads but requires more storage and processing.

    Attributes:
        base_url (str): Base URL for PMC FTP.
    """

    OA_FILE_LIST = "https://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_file_list.txt"

    def __init__(self, base_url: str = "https://ftp.ncbi.nlm.nih.gov/pub/pmc"):
        self.base_url = base_url

    def get_oa_file_list(self) -> List[Dict[str, str]]:
        """Get the list of all open access papers with their FTP paths.

        Returns:
            List[Dict[str, str]]: List of dicts with 'pmc_id', 'journal', 'path' keys.
        """
        print("Downloading OA file list (this may take a minute)...")

        response = requests.get(self.OA_FILE_LIST, timeout=60)
        response.raise_for_status()

        papers = []
        lines = response.text.strip().split('\n')

        # Skip header line
        for line in lines[1:]:
            parts = line.split('\t')
            if len(parts) >= 3:
                papers.append({
                    'path': parts[0],  # e.g., "oa_comm/xml/PMC13900.tar.gz"
                    'journal': parts[1],
                    'pmid': parts[2] if len(parts) > 2 else None
                })

        print(f"Found {len(papers)} open access papers")
        return papers

    def filter_by_journals(self,
                          papers: List[Dict[str, str]],
                          journals: List[str]) -> List[Dict[str, str]]:
        """Filter papers by journal name.

        Args:
            papers (List[Dict[str, str]]): List of papers.
            journals (List[str]): List of journal names to filter by.

        Returns:
            List[Dict[str, str]]: Filtered list of papers.
        """
        journals_lower = [j.lower() for j in journals]

        filtered = [
            p for p in papers
            if any(j in p['journal'].lower() for j in journals_lower)
        ]

        print(f"Filtered to {len(filtered)} papers from specified journals")
        return filtered


def example_usage():
    """Example usage of the fetcher"""

    # Configuration
    EMAIL = "your.email@example.com"  # Required by NCBI
    API_KEY = None  # Optional, get one from NCBI for higher rate limits
    OUTPUT_DIR = Path("./pmc_papers")

    # Initialize fetcher
    fetcher = PubMedCentralFetcher(
        email=EMAIL,
        api_key=API_KEY
    )

    # Example 1: Search and download papers on a specific topic
    print("=" * 60)
    print("Example 1: Search and download")
    print("=" * 60)

    result = fetcher.search_and_download(
        query="breast cancer BRCA1",
        output_dir=OUTPUT_DIR / "brca1_papers",
        max_results=50,
        start_date="2020/01/01"  # Papers from 2020 onwards
    )

    print(f"\nResults: {result}")

    # Example 2: Search first, review metadata, then download selectively
    print("\n" + "=" * 60)
    print("Example 2: Search, review, then download")
    print("=" * 60)

    pmc_ids = fetcher.search_papers(
        query="diabetes mellitus treatment",
        max_results=100
    )

    # Get metadata to review
    metadata = fetcher.get_paper_metadata(pmc_ids[:10])  # Just first 10 for example

    print("\nPaper titles:")
    for paper in metadata:
        print(f"- PMC{paper.pmc_id}: {paper.title[:80]}...")

    # Download selected papers
    selected_ids = [m.pmc_id for m in metadata]
    result = fetcher.download_papers_batch(
        pmc_ids=selected_ids,
        output_dir=OUTPUT_DIR / "diabetes_papers"
    )

    print(f"\nDownload results: {result}")

    # Example 3: Disease-specific corpus
    print("\n" + "=" * 60)
    print("Example 3: Build oncology corpus")
    print("=" * 60)

    oncology_queries = [
        "breast cancer",
        "lung cancer",
        "colorectal cancer",
        "melanoma"
    ]

    all_ids = set()
    for query in oncology_queries:
        ids = fetcher.search_papers(
            query=query,
            max_results=250,
            start_date="2018/01/01"
        )
        all_ids.update(ids)

    print(f"\nTotal unique papers found: {len(all_ids)}")

    # Download them all
    result = fetcher.download_papers_batch(
        pmc_ids=list(all_ids),
        output_dir=OUTPUT_DIR / "oncology_corpus"
    )

    print(f"\nFinal corpus: {result}")


def build_disease_corpus(disease: str,
                        max_papers: int = 1000,
                        output_dir: Path = Path("./corpus"),
                        email: str = "your.email@example.com") -> Path:
    """Convenience function to build a disease-specific corpus.

    Args:
        disease (str): Disease name (e.g., "breast cancer", "diabetes").
        max_papers (int): Maximum number of papers to download. Defaults to 1000.
        output_dir (Path): Where to save papers. Defaults to "./corpus".
        email (str): Your email for NCBI. Defaults to "your.email@example.com".

    Returns:
        Path: The directory where the corpus was saved.
    """
    fetcher = PubMedCentralFetcher(email=email)

    corpus_dir = output_dir / disease.replace(" ", "_")

    result = fetcher.search_and_download(
        query=disease,
        output_dir=corpus_dir,
        max_results=max_papers,
        start_date="2015/01/01"  # Last 10 years
    )

    print(f"\nBuilt corpus for '{disease}':")
    print(f"  Location: {corpus_dir}")
    print(f"  Downloaded: {result['success']} papers")
    print(f"  Failed: {result['failed']} papers")

    return corpus_dir


def main():
    """Main CLI interface"""
    import argparse
    import os

    parser = argparse.ArgumentParser(
        description='Download papers from PubMed Central',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download papers on a specific topic
  python -m src.scripts.download_papers \\
      --query "breast cancer BRCA1" \\
      --max-results 50 \\
      --output-dir papers/brca1

  # Filter by date range
  python -m src.scripts.download_papers \\
      --query "diabetes treatment" \\
      --start-date 2020/01/01 \\
      --end-date 2023/12/31 \\
      --output-dir papers/diabetes

  # Run examples
  python -m src.scripts.download_papers --examples
        """
    )

    parser.add_argument(
        '--query',
        help='Search query (e.g., "breast cancer BRCA1")'
    )
    parser.add_argument(
        '--max-results',
        type=int,
        default=100,
        help='Maximum number of results to download (default: 100)'
    )
    parser.add_argument(
        '--output-dir',
        help='Directory to save downloaded papers'
    )
    parser.add_argument(
        '--start-date',
        help='Filter by publication date - start (YYYY/MM/DD format)'
    )
    parser.add_argument(
        '--end-date',
        help='Filter by publication date - end (YYYY/MM/DD format)'
    )
    parser.add_argument(
        '--email',
        default=os.environ.get('NCBI_EMAIL', 'user@example.com'),
        help='Email address for NCBI (required). Can also use NCBI_EMAIL env var'
    )
    parser.add_argument(
        '--api-key',
        default=os.environ.get('NCBI_API_KEY'),
        help='NCBI API key (optional, increases rate limit). Can also use NCBI_API_KEY env var'
    )
    parser.add_argument(
        '--examples',
        action='store_true',
        help='Run example usage demonstrations'
    )

    args = parser.parse_args()

    # Run examples if requested
    if args.examples:
        example_usage()
        return

    # Validate required arguments
    if not args.query:
        parser.error('--query is required (or use --examples to see demonstrations)')
    if not args.output_dir:
        parser.error('--output-dir is required')

    # Initialize fetcher
    print(f"Initializing PubMed Central fetcher...")
    print(f"Email: {args.email}")
    if args.api_key:
        print(f"API Key: {'*' * 8}{args.api_key[-4:]}")

    fetcher = PubMedCentralFetcher(
        email=args.email,
        api_key=args.api_key
    )

    # Search and download
    print(f"\nSearching for: {args.query}")
    print(f"Max results: {args.max_results}")
    if args.start_date or args.end_date:
        print(f"Date range: {args.start_date or 'any'} to {args.end_date or 'any'}")
    print(f"Output directory: {args.output_dir}")
    print()

    result = fetcher.search_and_download(
        query=args.query,
        output_dir=Path(args.output_dir),
        max_results=args.max_results,
        start_date=args.start_date,
        end_date=args.end_date
    )

    print(f"\n{'='*60}")
    print(f"Download complete!")
    print(f"{'='*60}")
    print(f"Successful: {result['success']}")
    print(f"Failed: {result['failed']}")
    print(f"Total: {result['total']}")
    print(f"\nFiles saved to: {args.output_dir}")


if __name__ == '__main__':
    main()
