"""
Medical Knowledge Graph MCP Server

Model Context Protocol (MCP) server providing deep literature reasoning tools
for AI assistants like Claude Desktop.

Provides three specialized tools:
1. pubmed_graph_search: Multi-hop reasoning across papers
2. diagnostic_chain_trace: Follow symptom → diagnosis → treatment chains
3. evidence_contradiction_check: Surface contradictory evidence

Transport: stdio (connects to AI assistants via standard input/output)
"""

import asyncio
import json
import sys
from typing import Any, Dict, List, Optional
from pathlib import Path

# Add parent directory to path to import from src
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.client.medical_papers_client import MedicalPapersClient


class MCPServer:
    """MCP Server for medical literature reasoning.

    Implements the Model Context Protocol specification for stdio transport.
    Connects AI assistants (Claude Desktop, etc.) to the medical knowledge graph backend.

    Attributes:
        opensearch_host (str): Hostname for OpenSearch.
        opensearch_port (int): Port for OpenSearch.
        client (Optional[MedicalPapersClient]): Client for interacting with the medical papers knowledge base.
        tools (List[Dict[str, Any]]): List of tools provided by this server.
    """

    def __init__(self, opensearch_host: str = "localhost", opensearch_port: int = 9200):
        """Initialize MCP server with OpenSearch connection.

        Args:
            opensearch_host (str): Hostname for OpenSearch. Defaults to "localhost".
            opensearch_port (int): Port for OpenSearch. Defaults to 9200.
        """
        self.opensearch_host = opensearch_host
        self.opensearch_port = opensearch_port
        self.client: Optional[MedicalPapersClient] = None

        # Tool definitions for MCP protocol
        self.tools = [
            {
                "name": "pubmed_graph_search",
                "description": "Multi-hop reasoning across medical papers. Connects evidence chains that no single paper describes (e.g., Gene → Protein → Pathway → Drug). Returns entities, relationships, and supporting evidence with paragraph-level citations.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Natural language query (e.g., 'What drugs treat BRCA1-mutated breast cancer?')"
                        },
                        "max_depth": {
                            "type": "integer",
                            "description": "Maximum traversal depth for multi-hop reasoning (1-3, default: 2)",
                            "default": 2
                        },
                        "min_confidence": {
                            "type": "number",
                            "description": "Minimum confidence score for relationships (0.0-1.0, default: 0.7)",
                            "default": 0.7
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "diagnostic_chain_trace",
                "description": "Follow diagnostic reasoning chains from symptoms to diagnoses to treatments. Useful for complex multi-system presentations that don't fit textbook patterns. Returns diagnostic pathways with evidence strength.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "symptoms": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of clinical findings/symptoms (e.g., ['elevated ALP', 'fatigue', 'photosensitive rash'])"
                        },
                        "context": {
                            "type": "string",
                            "description": "Additional clinical context (age, gender, history, labs, etc.)",
                            "default": ""
                        }
                    },
                    "required": ["symptoms"]
                }
            },
            {
                "name": "evidence_contradiction_check",
                "description": "Find contradictory evidence in the literature. Shows both supporting and contradicting studies with evidence quality (study design, sample size, recency). Useful for understanding evolving medical consensus.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "claim": {
                            "type": "string",
                            "description": "Medical claim or question to check (e.g., 'Does aspirin prevent heart attacks in primary prevention?')"
                        },
                        "include_meta_analyses": {
                            "type": "boolean",
                            "description": "Include systematic reviews and meta-analyses",
                            "default": True
                        }
                    },
                    "required": ["claim"]
                }
            }
        ]

    async def initialize(self) -> bool:
        """Initialize OpenSearch client.

        Returns:
            bool: True if initialization was successful, False otherwise.
        """
        try:
            self.client = MedicalPapersClient(
                opensearch_host=self.opensearch_host,
                opensearch_port=self.opensearch_port
            )
            return True
        except Exception as e:
            self._log_error(f"Failed to initialize OpenSearch client: {e}")
            return False

    def _log_error(self, message: str) -> None:
        """Log errors to stderr.

        Args:
            message (str): The error message to log.
        """
        print(f"ERROR: {message}", file=sys.stderr)

    def _log_info(self, message: str) -> None:
        """Log info to stderr.

        Args:
            message (str): The info message to log.
        """
        print(f"INFO: {message}", file=sys.stderr)

    async def handle_list_tools(self) -> Dict[str, Any]:
        """Handle tools/list request.

        Returns:
            Dict[str, Any]: A dictionary containing the list of available tools.
        """
        return {
            "tools": self.tools
        }

    async def handle_call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/call request.

        Routes to appropriate tool handler based on tool_name.

        Args:
            tool_name (str): The name of the tool to call.
            arguments (Dict[str, Any]): The arguments for the tool.

        Returns:
            Dict[str, Any]: The result of the tool execution.
        """
        if not self.client:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": "Error: OpenSearch client not initialized"
                    }
                ],
                "isError": True
            }

        try:
            if tool_name == "pubmed_graph_search":
                return await self._handle_graph_search(arguments)
            elif tool_name == "diagnostic_chain_trace":
                return await self._handle_diagnostic_chain(arguments)
            elif tool_name == "evidence_contradiction_check":
                return await self._handle_contradiction_check(arguments)
            else:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Error: Unknown tool '{tool_name}'"
                        }
                    ],
                    "isError": True
                }
        except Exception as e:
            self._log_error(f"Tool call failed: {e}")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Error executing {tool_name}: {str(e)}"
                    }
                ],
                "isError": True
            }

    async def _handle_graph_search(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle pubmed_graph_search tool.

        TODO: Implement multi-hop graph traversal logic:
        1. Parse query to extract entities and relationships
        2. Query OpenSearch for entity matches
        3. Follow relationship chains up to max_depth
        4. Aggregate results with confidence scoring
        5. Format with paragraph-level provenance

        Args:
            arguments (Dict[str, Any]): Tool arguments containing 'query', 'max_depth', and 'min_confidence'.

        Returns:
            Dict[str, Any]: The search results.
        """
        query = arguments.get("query", "")
        max_depth = arguments.get("max_depth", 2)
        min_confidence = arguments.get("min_confidence", 0.7)

        self._log_info(f"Graph search: '{query}' (depth={max_depth}, min_conf={min_confidence})")

        # For now, use hybrid search as a placeholder
        # TODO: Replace with actual graph traversal implementation
        results = self.client.hybrid_search(query=query, k=10)

        # Format results
        formatted_results = self._format_search_results(results, query)

        return {
            "content": [
                {
                    "type": "text",
                    "text": formatted_results
                }
            ]
        }

    async def _handle_diagnostic_chain(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle diagnostic_chain_trace tool.

        TODO: Implement diagnostic reasoning:
        1. Parse symptoms to extract clinical entities
        2. Query for symptom → diagnosis relationships
        3. Query for diagnosis → treatment relationships
        4. Build diagnostic pathway with evidence
        5. Score pathways by evidence strength

        Args:
            arguments (Dict[str, Any]): Tool arguments containing 'symptoms' and 'context'.

        Returns:
            Dict[str, Any]: The diagnostic chain results.
        """
        symptoms = arguments.get("symptoms", [])
        context = arguments.get("context", "")

        self._log_info(f"Diagnostic chain: symptoms={symptoms}, context='{context}'")

        # Construct query from symptoms
        query = f"Clinical presentation: {', '.join(symptoms)}"
        if context:
            query += f". Context: {context}"

        # TODO: Replace with diagnostic chain traversal
        results = self.client.hybrid_search(query=query, k=15)

        formatted_results = self._format_diagnostic_results(results, symptoms)

        return {
            "content": [
                {
                    "type": "text",
                    "text": formatted_results
                }
            ]
        }

    async def _handle_contradiction_check(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle evidence_contradiction_check tool.

        TODO: Implement contradiction detection:
        1. Query for papers discussing the claim
        2. Extract findings (positive, negative, neutral)
        3. Group by evidence quality (RCTs > cohort > case reports)
        4. Identify contradictions (same intervention, different outcomes)
        5. Format with temporal evolution if applicable

        Args:
            arguments (Dict[str, Any]): Tool arguments containing 'claim' and 'include_meta_analyses'.

        Returns:
            Dict[str, Any]: The contradiction check results.
        """
        claim = arguments.get("claim", "")
        include_meta = arguments.get("include_meta_analyses", True)

        self._log_info(f"Contradiction check: '{claim}' (meta={include_meta})")

        # TODO: Replace with contradiction detection logic
        results = self.client.hybrid_search(query=claim, k=20)

        formatted_results = self._format_contradiction_results(results, claim)

        return {
            "content": [
                {
                    "type": "text",
                    "text": formatted_results
                }
            ]
        }

    def _format_search_results(self, results: List[Dict[str, Any]], query: str) -> str:
        """Format graph search results for display.

        Args:
            results (List[Dict[str, Any]]): List of search results.
            query (str): The original query.

        Returns:
            str: Formatted string of results.
        """
        if not results:
            return f"No results found for: {query}"

        output = [f"## Graph Search Results for: {query}\n"]
        output.append(f"Found {len(results)} relevant passages:\n")

        for i, result in enumerate(results[:10], 1):
            pmc_id = result.get('pmc_id', 'Unknown')
            title = result.get('title', 'Untitled')
            section = result.get('section', 'unknown')
            score = result.get('score', 0.0)
            chunk_text = result.get('chunk_text', '')[:300]  # First 300 chars

            output.append(f"### {i}. {title}")
            output.append(f"**Source:** {pmc_id} | **Section:** {section} | **Relevance:** {score:.3f}")
            output.append(f"{chunk_text}...\n")

        return "\n".join(output)

    def _format_diagnostic_results(self, results: List[Dict[str, Any]], symptoms: List[str]) -> str:
        """Format diagnostic chain results.

        Args:
            results (List[Dict[str, Any]]): List of search results.
            symptoms (List[str]): List of symptoms.

        Returns:
            str: Formatted string of results.
        """
        if not results:
            return f"No diagnostic pathways found for: {', '.join(symptoms)}"

        output = [f"## Diagnostic Pathways for: {', '.join(symptoms)}\n"]
        output.append(f"Found {len(results)} relevant passages:\n")

        # TODO: Group by diagnosis and rank by evidence strength
        for i, result in enumerate(results[:10], 1):
            pmc_id = result.get('pmc_id', 'Unknown')
            title = result.get('title', 'Untitled')
            chunk_text = result.get('chunk_text', '')[:300]

            output.append(f"### {i}. {title}")
            output.append(f"**Source:** {pmc_id}")
            output.append(f"{chunk_text}...\n")

        return "\n".join(output)

    def _format_contradiction_results(self, results: List[Dict[str, Any]], claim: str) -> str:
        """Format contradiction check results.

        Args:
            results (List[Dict[str, Any]]): List of search results.
            claim (str): The original claim.

        Returns:
            str: Formatted string of results.
        """
        if not results:
            return f"No evidence found for: {claim}"

        output = [f"## Evidence Analysis for: {claim}\n"]
        output.append(f"Found {len(results)} relevant studies:\n")

        # TODO: Group into supporting/contradicting/neutral
        output.append("### Studies Found:\n")
        for i, result in enumerate(results[:15], 1):
            pmc_id = result.get('pmc_id', 'Unknown')
            title = result.get('title', 'Untitled')

            output.append(f"{i}. **{title}** ({pmc_id})")

        output.append("\n_Note: Full contradiction analysis coming soon._")

        return "\n".join(output)

    async def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming MCP request.

        Routes requests to appropriate handlers based on method.

        Args:
            request (Dict[str, Any]): The incoming request dictionary.

        Returns:
            Dict[str, Any]: The response dictionary.
        """
        method = request.get("method", "")

        if method == "tools/list":
            return await self.handle_list_tools()
        elif method == "tools/call":
            params = request.get("params", {})
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})
            return await self.handle_call_tool(tool_name, arguments)
        else:
            return {
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }

    async def run(self) -> None:
        """Main server loop - reads from stdin, writes to stdout.

        Implements stdio transport for MCP protocol.
        """
        self._log_info("MCP Server starting...")

        # Initialize OpenSearch client
        if not await self.initialize():
            self._log_error("Failed to initialize - exiting")
            return

        self._log_info("MCP Server ready")

        # Read from stdin, write to stdout
        while True:
            try:
                line = sys.stdin.readline()
                if not line:
                    break  # EOF

                request = json.loads(line.strip())
                self._log_info(f"Request: {request.get('method', 'unknown')}")

                response = await self.handle_request(request)

                # Add request ID if present
                if "id" in request:
                    response["id"] = request["id"]

                response["jsonrpc"] = "2.0"

                # Write response to stdout
                print(json.dumps(response), flush=True)

            except json.JSONDecodeError as e:
                self._log_error(f"Invalid JSON: {e}")
            except Exception as e:
                self._log_error(f"Error processing request: {e}")


def main():
    """Entry point for MCP server"""
    import os

    # Get OpenSearch config from environment
    opensearch_host = os.getenv("OPENSEARCH_HOST", "localhost")
    opensearch_port = int(os.getenv("OPENSEARCH_PORT", "9200"))

    # Create and run server
    server = MCPServer(opensearch_host=opensearch_host, opensearch_port=opensearch_port)

    # Run async event loop
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
