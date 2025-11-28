"""
Natural Language to Graph Query Generator

Uses an LLM (via AWS Bedrock) to convert natural language medical questions
into structured graph queries using the defined JSON format.
"""

import boto3
import json
from typing import Optional, Dict, Any
from pathlib import Path
from graph_query_language import GraphQuery, CypherTranslator


class QueryGenerator:
    """Generate graph queries from natural language using an LLM"""

    def __init__(self,
                 aws_region: str = 'us-east-1',
                 model_id: str = 'anthropic.claude-3-5-sonnet-20241022-v2:0'):
        """
        Initialize the query generator

        Args:
            aws_region: AWS region for Bedrock
            model_id: Bedrock model ID to use
        """
        self.bedrock = boto3.client('bedrock-runtime', region_name=aws_region)
        self.model_id = model_id

        # Load the system prompt
        prompt_path = Path(__file__).parent / "llm_query_generation_prompt.md"
        with open(prompt_path, 'r') as f:
            self.system_prompt = f.read()

    def generate_query(self,
                      natural_language: str,
                      conversation_history: Optional[list] = None) -> Dict[str, Any]:
        """
        Generate a graph query from natural language

        Args:
            natural_language: The natural language question
            conversation_history: Optional list of prior messages for context

        Returns:
            Dict with:
                - 'query': GraphQuery object (if successful)
                - 'query_json': Raw JSON dict
                - 'explanation': LLM's explanation
                - 'cypher': Translated Cypher query
                - 'error': Error message (if failed)
        """
        # Build messages
        messages = conversation_history or []
        messages.append({
            "role": "user",
            "content": natural_language
        })

        # Call Bedrock
        try:
            response = self._call_llm(messages)

            # Parse the response
            return self._parse_llm_response(response)

        except Exception as e:
            return {
                "error": f"Error generating query: {str(e)}",
                "query": None,
                "query_json": None,
                "explanation": None,
                "cypher": None
            }

    def _call_llm(self, messages: list) -> str:
        """Call the LLM via Bedrock"""
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4000,
            "system": self.system_prompt,
            "messages": messages,
            "temperature": 0.0  # Deterministic for query generation
        }

        response = self.bedrock.invoke_model(
            modelId=self.model_id,
            contentType='application/json',
            accept='application/json',
            body=json.dumps(request_body)
        )

        response_body = json.loads(response['body'].read())
        return response_body['content'][0]['text']

    def _parse_llm_response(self, llm_response: str) -> Dict[str, Any]:
        """
        Parse the LLM response to extract query JSON and explanation

        LLM should return text like:
        I interpreted your question as: [explanation]

        Here's the graph query:

        {
          "match": { ... }
        }

        Note: [any assumptions]
        """
        # Extract explanation (text before JSON)
        explanation_lines = []
        json_start = llm_response.find('{')

        if json_start == -1:
            return {
                "error": "No JSON query found in LLM response",
                "query": None,
                "query_json": None,
                "explanation": llm_response,
                "cypher": None
            }

        explanation = llm_response[:json_start].strip()

        # Extract JSON (find matching braces)
        json_str = self._extract_json(llm_response[json_start:])

        if not json_str:
            return {
                "error": "Could not extract valid JSON from response",
                "query": None,
                "query_json": None,
                "explanation": explanation,
                "cypher": None
            }

        try:
            # Parse JSON
            query_dict = json.loads(json_str)

            # Validate with Pydantic
            query = GraphQuery(**query_dict)

            # Translate to Cypher
            translator = CypherTranslator()
            cypher = translator.translate(query)

            return {
                "query": query,
                "query_json": query_dict,
                "explanation": explanation,
                "cypher": cypher,
                "error": None
            }

        except json.JSONDecodeError as e:
            return {
                "error": f"Invalid JSON: {str(e)}",
                "query": None,
                "query_json": None,
                "explanation": explanation,
                "cypher": None
            }
        except Exception as e:
            return {
                "error": f"Query validation error: {str(e)}",
                "query": None,
                "query_json": query_dict if 'query_dict' in locals() else None,
                "explanation": explanation,
                "cypher": None
            }

    def _extract_json(self, text: str) -> Optional[str]:
        """Extract JSON object from text, handling nested braces"""
        if not text.startswith('{'):
            return None

        brace_count = 0
        for i, char in enumerate(text):
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    return text[:i+1]

        return None

    def interactive_session(self):
        """Run an interactive query generation session"""
        print("Medical Knowledge Graph Query Generator")
        print("=" * 60)
        print("Enter your medical questions in natural language.")
        print("Type 'exit' to quit.\n")

        conversation_history = []

        while True:
            try:
                question = input("\nYour question: ").strip()

                if question.lower() in ['exit', 'quit', 'q']:
                    print("Goodbye!")
                    break

                if not question:
                    continue

                print("\nGenerating query...")
                result = self.generate_query(question, conversation_history)

                if result['error']:
                    print(f"\n❌ Error: {result['error']}")
                    if result['explanation']:
                        print(f"\nLLM Response:\n{result['explanation']}")
                    continue

                print(f"\n✓ Query generated successfully!")
                print(f"\nExplanation:\n{result['explanation']}")

                print(f"\nJSON Query:")
                print(json.dumps(result['query_json'], indent=2))

                print(f"\nCypher Translation:")
                print(result['cypher'])

                # Add to conversation history for context
                conversation_history.append({
                    "role": "user",
                    "content": question
                })
                conversation_history.append({
                    "role": "assistant",
                    "content": f"{result['explanation']}\n\n```json\n{json.dumps(result['query_json'], indent=2)}\n```"
                })

                # Keep conversation history manageable
                if len(conversation_history) > 10:
                    conversation_history = conversation_history[-10:]

            except KeyboardInterrupt:
                print("\n\nGoodbye!")
                break
            except Exception as e:
                print(f"\n❌ Unexpected error: {e}")


def example_usage():
    """Example of using the query generator"""

    generator = QueryGenerator()

    # Example questions
    questions = [
        "What drugs treat breast cancer?",
        "What are the risks associated with BRCA1 mutations?",
        "Are there any contradictions about metformin treating diabetes?",
        "What biological pathways does BRCA1 affect?",
        "For a patient with BRCA1 mutations and breast cancer, what are high-confidence treatment options?"
    ]

    for i, question in enumerate(questions, 1):
        print(f"\n{'='*80}")
        print(f"Example {i}: {question}")
        print('='*80)

        result = generator.generate_query(question)

        if result['error']:
            print(f"❌ Error: {result['error']}")
            continue

        print(f"\n{result['explanation']}")
        print(f"\nJSON Query:")
        print(json.dumps(result['query_json'], indent=2))
        print(f"\nCypher:")
        print(result['cypher'])


if __name__ == '__main__':
    # For testing, run interactive session
    generator = QueryGenerator()
    generator.interactive_session()

    # Or run examples:
    # example_usage()
