"""
Script to import simple products data from Parquet file into PostgreSQL.

This script loads the simple_products.parquet file and imports it into the
PostgreSQL simple_products table, then tests cosine similarity search.
"""

import logging
import os
from pathlib import Path

import pandas as pd
import psycopg2
import numpy as np
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def load_connection_params() -> dict:
    """
    Load PostgreSQL connection parameters from environment variables.
    
    Returns:
        Dictionary with connection parameters
        
    Raises:
        ValueError: If required environment variables are missing
    """
    # Load environment variables
    load_dotenv()
    
    # Default connection parameters (matching docker-compose.yml)
    connection_params = {
        'host': os.getenv('PGHOST', 'localhost'),
        'port': int(os.getenv('PGPORT', 5432)),
        'database': os.getenv('PGDATABASE', 'aidb'),
        'user': os.getenv('PGUSER', 'admin'),
        'password': os.getenv('PGPASSWORD', 'Admin12345678')
    }
    
    # Validate required parameters
    required_params = ['host', 'port', 'database', 'user', 'password']
    missing_params = [param for param in required_params if not connection_params.get(param)]
    
    if missing_params:
        raise ValueError(f"Missing required connection parameters: {missing_params}")
    
    return connection_params


def load_simple_products(file_path: Path) -> pd.DataFrame:
    """
    Load simple products data from Parquet file.
    
    Args:
        file_path: Path to the simple_products.parquet file
        
    Returns:
        DataFrame with product data
        
    Raises:
        FileNotFoundError: If the input file doesn't exist
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Input file not found: {file_path}")
    
    logger.info(f"Loading data from {file_path}")
    df = pd.read_parquet(file_path)
    logger.info(f"Loaded {len(df)} records from {file_path}")
    
    return df


def prepare_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepare DataFrame for PostgreSQL import.
    
    Args:
        df: Original DataFrame
        
    Returns:
        DataFrame prepared for database import
    """
    logger.info("Preparing data for database import")
    
    # Create a copy to avoid modifying the original
    df_prepared = df.copy()
    
    # Rename columns to match PostgreSQL table schema
    column_mapping = {
        'producerName': 'producer_name',
        'productName': 'product_name',
        'productDescription': 'product_description',
        'productId': 'product_id',
        'combinedText': 'combined_text',
        'embedding': 'embedding'
    }
    
    df_prepared = df_prepared.rename(columns=column_mapping)
    
    # Convert embeddings to proper format for PostgreSQL
    # Ensure embeddings are lists of floats
    def convert_embedding(embedding):
        if embedding is None:
            return None
        if isinstance(embedding, (list, np.ndarray)):
            return list(map(float, embedding))
        return None
    
    df_prepared['embedding'] = df_prepared['embedding'].apply(convert_embedding)
    
    # Remove rows with null embeddings
    initial_count = len(df_prepared)
    df_prepared = df_prepared[df_prepared['embedding'].notna()]
    final_count = len(df_prepared)
    
    if initial_count != final_count:
        logger.warning(f"Removed {initial_count - final_count} rows with null embeddings")
    
    logger.info(f"Prepared {len(df_prepared)} records for import")
    return df_prepared


def import_to_postgres(df: pd.DataFrame, connection_params: dict) -> bool:
    """
    Import DataFrame to PostgreSQL table.
    
    Args:
        df: DataFrame to import
        connection_params: Database connection parameters
        
    Returns:
        True if import was successful, False otherwise
    """
    try:
        # Connect to database
        logger.info("Connecting to PostgreSQL database...")
        conn = psycopg2.connect(**connection_params)
        cursor = conn.cursor()
        
        # Clear existing data
        logger.info("Clearing existing data from simple_products table...")
        cursor.execute("TRUNCATE TABLE simple_products RESTART IDENTITY;")
        conn.commit()
        
        # Prepare insert query
        insert_query = """
        INSERT INTO simple_products (
            product_id, producer_name, product_name, product_description,
            combined_text, embedding
        ) VALUES (
            %s, %s, %s, %s, %s, %s::vector
        )
        """
        
        # Import data in batches
        batch_size = 100
        total_rows = len(df)
        successful_imports = 0
        
        logger.info(f"Starting import of {total_rows} records in batches of {batch_size}")
        
        for i in range(0, total_rows, batch_size):
            batch_end = min(i + batch_size, total_rows)
            batch_df = df.iloc[i:batch_end]
            
            batch_data = []
            for _, row in batch_df.iterrows():
                # Convert embedding list to PostgreSQL vector format
                # Ensure we have exactly 2000 dimensions
                embedding = row['embedding']
                if embedding and len(embedding) == 2000:
                    embedding_str = '[' + ','.join(map(str, embedding)) + ']'
                else:
                    logger.warning(f"Skipping row with invalid embedding dimensions: {len(embedding) if embedding else 0}")
                    continue
                
                batch_data.append((
                    row['product_id'],
                    row['producer_name'],
                    row['product_name'],
                    row['product_description'],
                    row['combined_text'],
                    embedding_str
                ))
            
            try:
                cursor.executemany(insert_query, batch_data)
                conn.commit()
                successful_imports += len(batch_data)
                logger.info(f"Imported batch {i//batch_size + 1}: {successful_imports}/{total_rows} records")
            except Exception as e:
                logger.error(f"Failed to import batch {i//batch_size + 1}: {e}")
                conn.rollback()
        
        # Verify import
        cursor.execute("SELECT COUNT(*) FROM simple_products;")
        count = cursor.fetchone()[0]
        logger.info(f"Import completed. Total records in database: {count}")
        
        # Close connection
        cursor.close()
        conn.close()
        logger.info("Database connection closed")
        
        return count == successful_imports
        
    except Exception as e:
        logger.error(f"Error during import: {e}")
        if 'conn' in locals():
            conn.close()
        return False


def test_similarity_search(connection_params: dict) -> None:
    """
    Test cosine similarity search on the imported data.
    
    Args:
        connection_params: Database connection parameters
    """
    try:
        logger.info("Testing cosine similarity search...")
        
        # Connect to database
        conn = psycopg2.connect(**connection_params)
        cursor = conn.cursor()
        
        # Get a sample embedding for testing
        cursor.execute("""
            SELECT embedding, producer_name, product_name, product_description
            FROM simple_products
            LIMIT 1
        """)
        result = cursor.fetchone()
        
        if not result:
            logger.error("No data found in simple_products table for testing")
            return
        
        test_embedding_str = result[0]
        original_producer = result[1]
        original_product = result[2]
        original_description = result[3]
        
        logger.info(f"Using test query from: {original_producer} - {original_product}")
        
        # Perform similarity search
        search_query = """
        SELECT 
            producer_name,
            product_name,
            product_description,
            1 - (embedding <=> %s::vector) AS similarity_score
        FROM simple_products
        ORDER BY embedding <=> %s::vector
        LIMIT 5
        """
        
        cursor.execute(search_query, (test_embedding_str, test_embedding_str))
        results = cursor.fetchall()
        
        logger.info("Similarity search results:")
        logger.info("=" * 80)
        for i, (producer, product, description, similarity) in enumerate(results, 1):
            logger.info(f"{i}. {producer} - {product}")
            logger.info(f"   Description: {description[:100]}...")
            logger.info(f"   Similarity: {similarity:.4f}")
            logger.info("-" * 80)
        
        # Test with a different query
        logger.info("\nTesting search for 'milk' related products...")
        
        # Find products related to milk
        milk_query = """
        SELECT 
            producer_name,
            product_name,
            product_description,
            1 - (embedding <=> (
                SELECT embedding FROM simple_products 
                WHERE LOWER(combined_text) LIKE '%milk%' 
                LIMIT 1
            )) AS similarity_score
        FROM simple_products
        WHERE id != (
            SELECT id FROM simple_products 
            WHERE LOWER(combined_text) LIKE '%milk%' 
            LIMIT 1
        )
        ORDER BY embedding <=> (
            SELECT embedding FROM simple_products 
            WHERE LOWER(combined_text) LIKE '%milk%' 
            LIMIT 1
        )
        LIMIT 3
        """
        
        cursor.execute(milk_query)
        milk_results = cursor.fetchall()
        
        if milk_results:
            logger.info("Products similar to milk:")
            logger.info("=" * 80)
            for i, (producer, product, description, similarity) in enumerate(milk_results, 1):
                logger.info(f"{i}. {producer} - {product}")
                logger.info(f"   Description: {description[:100]}...")
                logger.info(f"   Similarity: {similarity:.4f}")
                logger.info("-" * 80)
        else:
            logger.info("No milk-related products found for comparison")
        
        cursor.close()
        conn.close()
        logger.info("Similarity search test completed")
        
    except Exception as e:
        logger.error(f"Error during similarity search test: {e}")
        if 'conn' in locals():
            conn.close()


def main():
    """Main function to import simple products data to PostgreSQL and test similarity search."""
    try:
        logger.info("Starting simple products import to PostgreSQL")
        
        # Define file path
        script_dir = Path(__file__).parent
        input_file = script_dir.parent / 'processed' / 'simple_products.parquet'
        
        # Load connection parameters
        connection_params = load_connection_params()
        logger.info(f"Connecting to PostgreSQL at {connection_params['host']}:{connection_params['port']}")
        
        # Load data
        df = load_simple_products(input_file)
        
        # Print basic information
        logger.info("Dataset Summary:")
        logger.info(f"  Total records: {len(df):,}")
        logger.info(f"  Columns: {list(df.columns)}")
        logger.info(f"  Memory usage: {df.memory_usage(deep=True).sum() / 1024 / 1024:.2f} MB")
        
        # Show sample data
        logger.info("\nFirst 3 records:")
        for idx, row in df.head(3).iterrows():
            logger.info(f"  Record {idx + 1}:")
            logger.info(f"    Producer: {row['producerName']}")
            logger.info(f"    Product: {row['productName']}")
            logger.info(f"    Description: {row['productDescription'][:100]}...")
            
            # Handle embedding dimensions safely
            embedding = row['embedding']
            if embedding is not None and hasattr(embedding, '__len__'):
                embedding_dims = len(embedding)
            else:
                embedding_dims = 0
            logger.info(f"    Embedding dimensions: {embedding_dims}")
        
        # Prepare data for import
        df_prepared = prepare_data(df)
        
        # Import to PostgreSQL
        success = import_to_postgres(df_prepared, connection_params)
        
        if success:
            logger.info("✅ Simple products import completed successfully")
            
            # Test similarity search
            test_similarity_search(connection_params)
        else:
            logger.error("❌ Simple products import failed")
            return False
        
        logger.info("Simple products import and testing completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error in import process: {e}")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
