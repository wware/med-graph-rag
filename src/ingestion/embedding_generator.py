"""
Embedding Generator using AWS Bedrock Titan Embeddings V2

Generates embeddings for text chunks to enable semantic search in OpenSearch.
"""

import boto3
import json
from typing import List
import time

import pytest
from unittest.mock import Mock, patch, MagicMock
import json
from botocore.exceptions import ClientError


class EmbeddingGenerator:
    """Generate embeddings using AWS Bedrock Titan Embeddings V2.

    Attributes:
        bedrock (boto3.client): The AWS Bedrock runtime client.
        model_id (str): The ID of the model to use for embeddings.
    """

    def __init__(self, region_name: str = 'us-east-1'):
        """Initialize Bedrock client.

        Args:
            region_name (str): AWS region name. Defaults to 'us-east-1'.
        """
        self.bedrock = boto3.client(
            service_name='bedrock-runtime',
            region_name=region_name
        )
        self.model_id = 'amazon.titan-embed-text-v2:0'

    def embed_text(self, text: str, input_type: str = 'search_document') -> List[float]:
        """Generate embedding for a single text string.

        Args:
            text (str): Text to embed (max ~8000 tokens).
            input_type (str): 'search_document' for indexing, 'search_query' for queries.
                Defaults to 'search_document'.

        Returns:
            List[float]: List of floats representing the embedding vector (1024 dimensions).

        Raises:
            Exception: If there is an error invoking the Bedrock model.
        """
        # Truncate if too long (Titan v2 max is ~8000 tokens, roughly 30k chars)
        if len(text) > 30000:
            text = text[:30000]

        request_body = {
            "inputText": text,
            "dimensions": 1024,
            "normalize": True
        }

        try:
            response = self.bedrock.invoke_model(
                modelId=self.model_id,
                contentType='application/json',
                accept='application/json',
                body=json.dumps(request_body)
            )

            response_body = json.loads(response['body'].read())
            return response_body['embedding']

        except Exception as e:
            print(f"Error generating embedding: {e}")
            raise

    def embed_batch(self, texts: List[str], input_type: str = 'search_document',
                   batch_size: int = 10, delay: float = 0.1) -> List[List[float]]:
        """Generate embeddings for multiple texts with rate limiting.

        Args:
            texts (List[str]): List of texts to embed.
            input_type (str): 'search_document' for indexing, 'search_query' for queries.
                Defaults to 'search_document'.
            batch_size (int): Process this many at once before delay. Defaults to 10.
            delay (float): Seconds to wait between batches. Defaults to 0.1.

        Returns:
            List[List[float]]: List of embedding vectors.
        """
        embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]

            for text in batch:
                embedding = self.embed_text(text, input_type)
                embeddings.append(embedding)

            # Rate limiting
            if i + batch_size < len(texts):
                time.sleep(delay)

            if (i + batch_size) % 100 == 0:
                print(f"Processed {i + batch_size}/{len(texts)} embeddings")

        return embeddings

### pytest ###

def test_embed_text_success():
    """Test successful embedding generation for a single text"""
    with patch('boto3.client') as mock_client:
        # Mock the Bedrock response
        mock_response = {
            'body': MagicMock(read=lambda: json.dumps({
                'embedding': [0.1] * 1024
            }).encode())
        }
        mock_client.return_value.invoke_model.return_value = mock_response
        
        generator = EmbeddingGenerator()
        result = generator.embed_text("Test text")
        
        assert len(result) == 1024
        assert all(isinstance(x, float) for x in result)


def test_embed_text_truncation():
    """Test that long texts are truncated to 30k characters"""
    with patch('boto3.client') as mock_client:
        mock_response = {
            'body': MagicMock(read=lambda: json.dumps({
                'embedding': [0.1] * 1024
            }).encode())
        }
        mock_client.return_value.invoke_model.return_value = mock_response
        
        generator = EmbeddingGenerator()
        long_text = "a" * 50000
        generator.embed_text(long_text)
        
        # Verify the text was truncated in the request
        call_args = mock_client.return_value.invoke_model.call_args
        body = json.loads(call_args.kwargs['body'])
        assert len(body['inputText']) == 30000


def test_embed_text_input_types():
    """Test different input_type parameters"""
    with patch('boto3.client') as mock_client:
        mock_response = {
            'body': MagicMock(read=lambda: json.dumps({
                'embedding': [0.1] * 1024
            }).encode())
        }
        mock_client.return_value.invoke_model.return_value = mock_response
        
        generator = EmbeddingGenerator()
        
        # Test search_document (default)
        generator.embed_text("Test", input_type='search_document')
        # Test search_query
        generator.embed_text("Test", input_type='search_query')
        
        assert mock_client.return_value.invoke_model.call_count == 2


def test_embed_text_error_handling():
    """Test error handling when Bedrock call fails"""
    with patch('boto3.client') as mock_client:
        mock_client.return_value.invoke_model.side_effect = ClientError(
            {'Error': {'Code': 'ServiceUnavailable', 'Message': 'Service error'}},
            'invoke_model'
        )
        
        generator = EmbeddingGenerator()
        
        with pytest.raises(ClientError):
            generator.embed_text("Test text")


def test_embed_batch_basic():
    """Test batch embedding generation"""
    with patch('boto3.client') as mock_client:
        mock_response = {
            'body': MagicMock(read=lambda: json.dumps({
                'embedding': [0.1] * 1024
            }).encode())
        }
        mock_client.return_value.invoke_model.return_value = mock_response
        
        generator = EmbeddingGenerator()
        texts = ["Text 1", "Text 2", "Text 3"]
        
        with patch('time.sleep'):  # Skip actual sleep
            results = generator.embed_batch(texts, batch_size=2, delay=0.1)
        
        assert len(results) == 3
        assert all(len(emb) == 1024 for emb in results)


def test_embed_batch_rate_limiting():
    """Test that rate limiting delays are applied"""
    with patch('boto3.client') as mock_client:
        mock_response = {
            'body': MagicMock(read=lambda: json.dumps({
                'embedding': [0.1] * 1024
            }).encode())
        }
        mock_client.return_value.invoke_model.return_value = mock_response
        
        generator = EmbeddingGenerator()
        texts = ["Text " + str(i) for i in range(25)]
        
        with patch('time.sleep') as mock_sleep:
            generator.embed_batch(texts, batch_size=10, delay=0.5)
            
            # Should sleep twice: after batch 1 (0-9) and batch 2 (10-19)
            assert mock_sleep.call_count == 2
            mock_sleep.assert_called_with(0.5)


def test_embed_batch_empty_list():
    """Test batch embedding with empty list"""
    with patch('boto3.client'):
        generator = EmbeddingGenerator()
        results = generator.embed_batch([])
        
        assert results == []


def test_embed_batch_progress_logging(capsys):
    """Test that progress is logged for large batches"""
    with patch('boto3.client') as mock_client:
        mock_response = {
            'body': MagicMock(read=lambda: json.dumps({
                'embedding': [0.1] * 1024
            }).encode())
        }
        mock_client.return_value.invoke_model.return_value = mock_response
        
        generator = EmbeddingGenerator()
        texts = ["Text " + str(i) for i in range(150)]
        
        with patch('time.sleep'):
            generator.embed_batch(texts, batch_size=10)
        
        captured = capsys.readouterr()
        assert "Processed 100/150 embeddings" in captured.out


def test_region_configuration():
    """Test that region can be configured"""
    with patch('boto3.client') as mock_client:
        EmbeddingGenerator(region_name='us-west-2')
        
        mock_client.assert_called_once_with(
            service_name='bedrock-runtime',
            region_name='us-west-2'
        )


def test_model_id():
    """Test that correct model ID is used"""
    with patch('boto3.client') as mock_client:
        mock_response = {
            'body': MagicMock(read=lambda: json.dumps({
                'embedding': [0.1] * 1024
            }).encode())
        }
        mock_client.return_value.invoke_model.return_value = mock_response
        
        generator = EmbeddingGenerator()
        generator.embed_text("Test")
        
        call_args = mock_client.return_value.invoke_model.call_args
        assert call_args.kwargs['modelId'] == 'amazon.titan-embed-text-v2:0'


if __name__ == "__main__":
    pytest.main([__file__])
