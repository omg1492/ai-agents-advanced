"""
Script to generate embeddings for product data from producers.json.

This script processes the producers.json file, creates a flat table of products,
generates combined text descriptions, and creates embeddings using OpenAI's
text-embedding-3-large model.
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import List, Dict, Any

import pandas as pd
from dotenv import load_dotenv
from openai import AzureOpenAI, OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Reduce verbosity of SDK loggers
logging.getLogger('openai').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)

# Load environment variables
load_dotenv()


class EmbeddingsGenerator:
    """Handles embedding generation with proper retry logic and rate limiting."""
    
    def __init__(self):
        """Initialize the embeddings generator with appropriate OpenAI client."""
        self.api_type = os.getenv('OPENAI_API_TYPE', 'azure')
        self.batch_size = 100  # Report progress every 100 records
        
        if self.api_type == 'azure':
            self._init_azure_client()
        else:
            self._init_openai_client()
    
    def _init_azure_client(self):
        """Initialize Azure OpenAI client for embeddings."""
        self.client = AzureOpenAI(
            azure_endpoint=os.getenv('AZURE_OPENAI_EMBEDDING_ENDPOINT'),
            api_key=os.getenv('AZURE_OPENAI_EMBEDDING_API_KEY'),
            api_version=os.getenv('AZURE_OPENAI_EMBEDDING_API_VERSION', '2024-12-01-preview')
        )
        self.model = os.getenv('AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME', 'text-embedding-3-large')
        logger.info(f"Initialized Azure OpenAI client with model: {self.model} (2000 dimensions)")
    
    def _init_openai_client(self):
        """Initialize OpenAI client for embeddings."""
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.model = os.getenv('OPENAI_EMBEDDING_MODEL', 'text-embedding-3-large')
        logger.info(f"Initialized OpenAI client with model: {self.model} (2000 dimensions)")
    
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        retry=retry_if_exception_type(Exception)
    )
    def _get_embedding(self, text: str) -> List[float]:
        """
        Get embedding for a single text with retry logic.
        
        Args:
            text: Text to embed
            
        Returns:
            List of embedding values (2000 dimensions for pgvector compatibility)
            
        Raises:
            Exception: If embedding generation fails after retries
        """
        try:
            response = self.client.embeddings.create(
                input=text,
                model=self.model,
                dimensions=2000  # Limit to 2000 dimensions for pgvector HNSW index compatibility
            )
            return response.data[0].embedding
        except Exception as e:
            # Check if it's a rate limit error (429)
            if hasattr(e, 'status_code') and e.status_code == 429:
                # Extract retry-after header if available
                retry_after = getattr(e, 'retry_after', None)
                if retry_after:
                    logger.warning(f"Rate limited. Waiting {retry_after} seconds before retry.")
                    time.sleep(float(retry_after))
                else:
                    logger.warning("Rate limited. Using exponential backoff.")
            logger.error(f"Error generating embedding: {e}")
            raise
    
    def generate_embeddings(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate embeddings for all rows in the dataframe using parallel processing.
        
        Args:
            df: DataFrame with combinedText column
            
        Returns:
            DataFrame with added embedding column
        """
        import concurrent.futures
        import threading
        
        logger.info(f"Starting parallel embedding generation for {len(df)} records")
        
        # Prepare data for parallel processing
        texts = df['combinedText'].tolist()
        embeddings = [None] * len(texts)  # Pre-allocate list
        
        lock = threading.Lock()
        completed = [0]  # Use list to make it mutable in nested function
        
        def process_embedding(args):
            idx, text = args
            try:
                embedding = self._get_embedding(text)
                with lock:
                    embeddings[idx] = embedding
                    completed[0] += 1
                    # Report progress
                    if completed[0] % self.batch_size == 0:
                        logger.info(f"Processed {completed[0]}/{len(texts)} records")
                return True
            except Exception as e:
                logger.error(f"Failed to generate embedding for row {idx}: {e}")
                with lock:
                    embeddings[idx] = []  # Empty embedding on failure
                    completed[0] += 1
                return False
        
        # Use ThreadPoolExecutor with 50 workers for parallel processing
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            # Create list of (index, text) pairs
            tasks = [(idx, text) for idx, text in enumerate(texts)]
            logger.info(f"Submitting {len(tasks)} tasks to thread pool...")
            
            # Use executor.map to ensure all tasks complete
            results = list(executor.map(process_embedding, tasks))
            logger.info(f"All {len(results)} tasks completed")
        
        df['embedding'] = embeddings
        successful_embeddings = len([e for e in embeddings if e is not None and len(e) > 0])
        logger.info(f"Completed embedding generation: {successful_embeddings}/{len(df)} successful")
        return df


def load_producers_data(file_path: Path) -> List[Dict[str, Any]]:
    """
    Load producers data from JSON file.
    
    Args:
        file_path: Path to the producers.json file
        
    Returns:
        List of producer dictionaries
        
    Raises:
        FileNotFoundError: If the input file doesn't exist
        json.JSONDecodeError: If the JSON is invalid
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Input file not found: {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    logger.info(f"Loaded {len(data)} producers from {file_path}")
    return data


def create_products_dataframe(producers_data: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Create a flat DataFrame from nested producers data.
    
    Args:
        producers_data: List of producer dictionaries
        
    Returns:
        DataFrame with columns: producerName, productName, productDescription, productId
    """
    products = []
    
    for producer in producers_data:
        producer_name = producer.get('name', '')
        
        for product in producer.get('products', []):
            products.append({
                'producerName': producer_name,
                'productName': product.get('name', ''),
                'productDescription': product.get('description', ''),
                'productId': product.get('productId', '')
            })
    
    df = pd.DataFrame(products)
    logger.info(f"Created DataFrame with {len(df)} products")
    return df


def add_combined_text_column(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add combinedText column with formatted text for embeddings.
    
    Args:
        df: DataFrame with product information
        
    Returns:
        DataFrame with added combinedText column
    """
    df['combinedText'] = (
        "PRODUCER: " + df['producerName'] + 
        ", PRODUCT: " + df['productName'] + 
        ", DESCRIPTION: " + df['productDescription']
    )
    
    logger.info("Added combinedText column")
    return df


def save_to_parquet(df: pd.DataFrame, output_path: Path) -> None:
    """
    Save DataFrame to Parquet file.
    
    Args:
        df: DataFrame to save
        output_path: Path where to save the Parquet file
    """
    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    df.to_parquet(output_path, index=False)
    logger.info(f"Saved {len(df)} records to {output_path}")


def main():
    """Main function to orchestrate the embedding generation process."""
    try:
        # Define file paths
        script_dir = Path(__file__).parent
        input_file = script_dir.parent / 'source_json' / 'producers.json'
        output_file = script_dir.parent / 'processed' / 'simple_products.parquet'
        
        logger.info("Starting embeddings generation process")
        
        # Load data
        producers_data = load_producers_data(input_file)
        
        # Create DataFrame
        df = create_products_dataframe(producers_data)
        
        # Add combined text column
        df = add_combined_text_column(df)
        
        # Generate embeddings
        generator = EmbeddingsGenerator()
        df = generator.generate_embeddings(df)
        
        # Save to Parquet
        save_to_parquet(df, output_file)
        
        logger.info("Embeddings generation completed successfully")
        
        # Print summary statistics
        logger.info("Summary:")
        logger.info(f"  Total products processed: {len(df)}")
        logger.info(f"  Embeddings generated: {len([e for e in df['embedding'] if len(e) > 0])}")
        logger.info(f"  Failed embeddings: {len([e for e in df['embedding'] if len(e) == 0])}")
        logger.info(f"  Output file: {output_file}")
        
    except Exception as e:
        logger.error(f"Error in main process: {e}")
        raise


if __name__ == "__main__":
    main()
