import json
import os
import uuid
import random
from typing import List, Dict, Any
from pathlib import Path
import openai
from dotenv import load_dotenv
from pydantic import BaseModel, Field


class Allergen(BaseModel):
    """Pydantic model for allergen data."""
    name: str = Field(..., description="Clear, descriptive name of the allergen")
    safetyScore: int = Field(..., ge=0, le=10, description="Safety score from 0 (very dangerous) to 10 (very safe)")
    description: str = Field(..., description="Brief, informative description of the allergen")


class AllergenBatch(BaseModel):
    """Batch of allergens for structured output."""
    allergens: List[Allergen] = Field(..., description="List of allergen objects")


class Certification(BaseModel):
    """Pydantic model for certification data."""
    name: str = Field(..., description="Official-sounding certification name")
    description: str = Field(..., description="Detailed description of what this certification means and requires")


class CertificationBatch(BaseModel):
    """Batch of certifications for structured output."""
    certifications: List[Certification] = Field(..., description="List of certification objects")


class Product(BaseModel):
    """Pydantic model for product data."""
    name: str = Field(..., description="Creative, appetizing product name")
    description: str = Field(..., description="Detailed description including taste, uses, origin story, or fun facts")
    allergenIds: List[str] = Field(..., description="List of allergen IDs that apply to this product (0-5 allergens, choose logically based on product type)")


class Producer(BaseModel):
    """Pydantic model for producer data."""
    name: str = Field(..., description="Creative, realistic producer/farm name")
    description: str = Field(..., description="Detailed description of the producer, their history, specialization, and philosophy")
    products: List[Product] = Field(..., description="List of 0-40 products that this producer makes, logically matching their specialization", min_items=0, max_items=50)


class ProducerBatch(BaseModel):
    """Batch of producers for structured output."""
    producers: List[Producer] = Field(..., description="List of producer objects")


class ProductBatch(BaseModel):
    """Batch of products for structured output."""
    products: List[Product] = Field(..., description="List of product objects")


class FarmDataGenerator:
    """
    Generates synthetic farm product data including allergens, certifications, 
    producers, products, and stock information.
    """
    
    def __init__(self):
        """Initialize the data generator with OpenAI client."""
        load_dotenv("../../agents/dreamfarm-agent/.env")
        
        # Configure OpenAI client based on provider type
        api_type = os.getenv("OPENAI_API_TYPE", "openai")
        
        if api_type.lower() == "azure":
            self.client = openai.AzureOpenAI(
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
                api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
            )
            self.model = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4")
        else:
            self.client = openai.OpenAI(
                api_key=os.getenv("OPENAI_API_KEY")
            )
            self.model = os.getenv("OPENAI_MODEL", "gpt-4")
        
        # Create output directory
        self.output_dir = Path("../source_json")
        self.output_dir.mkdir(exist_ok=True)
        
        # Storage for generated data
        self.allergens = []
        self.certifications = []
        self.producers = []
        
        # Token tracking
        self.total_input_tokens = 0
        self.total_output_tokens = 0
    
    def _track_tokens(self, response) -> None:
        """Track token usage from API response."""
        if hasattr(response, 'usage') and response.usage:
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens
    
    def _print_token_summary(self) -> None:
        """Print current token usage summary."""
        total_tokens = self.total_input_tokens + self.total_output_tokens
        print(f"📊 Token usage - Input: {self.total_input_tokens:,}, Output: {self.total_output_tokens:,}, Total: {total_tokens:,}")
    
    def generate_allergens(self, target_count: int = 100) -> List[Dict[str, Any]]:
        """
        Generate allergen data using structured outputs.
        
        Args:
            target_count: Number of allergens to generate
            
        Returns:
            List of allergen dictionaries
        """
        print(f"Generating {target_count} allergens...")
        
        allergens = []
        batch_size = 20  # Generate in smaller batches to avoid token limits
        
        while len(allergens) < target_count:
            remaining = target_count - len(allergens)
            current_batch_size = min(batch_size, remaining)
            
            existing_context = ""
            if allergens:
                existing_names = [a["name"] for a in allergens[-10:]]  # Last 10 for context
                existing_context = f"Already generated allergens (avoid duplicates): {', '.join(existing_names)}\n\n"
            
            prompt = f"""{existing_context}Generate {current_batch_size} different allergens commonly found in farm products. 
            Be creative, sometimes funny, but logical and consistent. Include typical allergens like nuts, dairy, gluten, etc.
            but also less common ones from various farm products.
            
            Each allergen should have:
            - name: Clear, descriptive name
            - safetyScore: Integer from 0-10 (10 = very safe, 0 = very dangerous)
            - description: Brief, informative description (sometimes humorous but accurate)"""
            
            try:
                response = self.client.beta.chat.completions.parse(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are a creative but accurate farm product data generator. Generate realistic allergen data."},
                        {"role": "user", "content": prompt}
                    ],
                    response_format=AllergenBatch,
                    temperature=0.8
                )
                
                # Handle potential refusal
                if response.choices[0].message.refusal:
                    print(f"Model refused to generate allergens: {response.choices[0].message.refusal}")
                    continue
                
                # Track token usage
                self._track_tokens(response)
                
                batch_data = response.choices[0].message.parsed.allergens
                batch_allergens = [allergen.model_dump() for allergen in batch_data]
                allergens.extend(batch_allergens)
                print(f"Generated batch of {len(batch_allergens)} allergens. Total: {len(allergens)}")
                self._print_token_summary()
                
            except Exception as e:
                print(f"Error generating allergens batch: {e}")
                # Continue with next batch
                continue
        
        # Trim to exact count and add IDs
        allergens = allergens[:target_count]
        for allergen in allergens:
            allergen["allergenId"] = str(uuid.uuid4())
        
        self.allergens = allergens
        print(f"Successfully generated {len(allergens)} allergens")
        return allergens
    
    def generate_certifications(self, target_count: int = 100) -> List[Dict[str, Any]]:
        """
        Generate certification data using structured outputs.
        
        Args:
            target_count: Number of certifications to generate
            
        Returns:
            List of certification dictionaries
        """
        print(f"Generating {target_count} certifications...")
        
        certifications = []
        batch_size = 15
        
        while len(certifications) < target_count:
            remaining = target_count - len(certifications)
            current_batch_size = min(batch_size, remaining)
            
            existing_context = ""
            if certifications:
                existing_names = [c["name"] for c in certifications[-10:]]
                existing_context = f"Already generated certifications (avoid duplicates): {', '.join(existing_names)}\n\n"
            
            prompt = f"""{existing_context}Generate {current_batch_size} different farm product certifications. 
            Include various types: organic, regional products, fair trade, quality standards, environmental certifications, etc.
            Be creative and realistic - think of actual certification types that exist worldwide.
            
            Each certification should have:
            - name: Official-sounding certification name
            - description: Detailed description of what this certification means and requires"""
            
            try:
                response = self.client.beta.chat.completions.parse(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are generating realistic farm product certification data. Make them sound official and professional."},
                        {"role": "user", "content": prompt}
                    ],
                    response_format=CertificationBatch,
                    temperature=0.7
                )
                
                # Handle potential refusal
                if response.choices[0].message.refusal:
                    print(f"Model refused to generate certifications: {response.choices[0].message.refusal}")
                    continue
                
                # Track token usage
                self._track_tokens(response)
                
                batch_data = response.choices[0].message.parsed.certifications
                batch_certifications = [cert.model_dump() for cert in batch_data]
                certifications.extend(batch_certifications)
                print(f"Generated batch of {len(batch_certifications)} certifications. Total: {len(certifications)}")
                self._print_token_summary()
                
            except Exception as e:
                print(f"Error generating certifications batch: {e}")
                continue
        
        # Trim to exact count and add IDs
        certifications = certifications[:target_count]
        for certification in certifications:
            certification["certificationId"] = str(uuid.uuid4())
        
        self.certifications = certifications
        print(f"Successfully generated {len(certifications)} certifications")
        return certifications
    
    def generate_producers(self, target_count: int = 200) -> List[Dict[str, Any]]:
        """
        Generate producer data with valid certification IDs and their products using structured outputs, in parallel.
        """
        import concurrent.futures
        import threading
        import time
        from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

        print(f"Generating {target_count} producers with their products (parallel)...")

        if not self.certifications or not self.allergens:
            raise ValueError("Certifications and allergens must be generated first")

        cert_ids = [cert["certificationId"] for cert in self.certifications]
        allergen_info = [
            {"id": allergen["allergenId"], "name": allergen["name"], "description": allergen["description"]}
            for allergen in self.allergens
        ]
        allergen_context = "Available allergens for product assignment:\n" + "".join(
            f"- ID: {a['id']}, Name: {a['name']}, Description: {a['description']}\n" for a in allergen_info
        )

        batch_size = 3
        batches = []
        for i in range(0, target_count, batch_size):
            batches.append(min(batch_size, target_count - i))

        lock = threading.Lock()
        all_producers = []
        all_token_usage = {"input": 0, "output": 0}

        def build_prompt(existing_names, current_batch_size):
            existing_context = f"Already generated producers (avoid duplicates): {', '.join(existing_names)}\n\n" if existing_names else ""
            return f"""{existing_context}{allergen_context}

Generate {current_batch_size} different farm product producers with their products. 
Include various types: family farms, cooperatives, organic producers, specialty farms, etc.
Make them diverse in location, size, and specialization. Be creative and sometimes funny with names.

Each producer should have:
- name: Creative, realistic producer/farm name
- description: Detailed description of the producer, their history, specialization, and philosophy
- products: List of 20-40 products that this producer makes (MINIMUM 0, aim for 20-40!)

CRITICAL FOR PRODUCTS - GENERATE MANY PRODUCTS PER PRODUCER:
- You MUST generate at least 15 products per producer, ideally 20-40
- Think comprehensively about all possible variations a real producer would make
- Products should match the producer's specialization perfectly
- Be creative with product variations: different flavors, sizes, seasonal items, specialty versions, aged versions, limited editions
- Examples:
  * Dairy farm: whole milk, 2% milk, skim milk, chocolate milk, strawberry milk, vanilla milk, buttermilk, heavy cream, light cream, various aged cheeses (cheddar 6mo, 1yr, 2yr), fresh cheeses, flavored yogurts, Greek yogurt, frozen yogurt, butter (salted, unsalted, cultured), ice cream (vanilla, chocolate, strawberry, mint, etc.), cottage cheese, sour cream, etc.
  * Bakery: sourdough bread, whole wheat bread, rye bread, baguettes, croissants, muffins (blueberry, chocolate, banana), cookies (chocolate chip, oatmeal, sugar), cakes, pies, pastries, bagels, donuts, etc.
  * Vegetable farm: different varieties of tomatoes, peppers, lettuce types, root vegetables, herbs, seasonal specialties, pickled versions, dried versions, etc.

For each product within a producer:
- name: Creative, appetizing product name that fits the producer's specialization
- description: Detailed description including taste, uses, origin story, or fun facts
- allergenIds: List of allergen IDs that logically apply to this product (0-5 allergens)

IMPORTANT: 
- Choose allergens intelligently based on product type
- Use actual allergen IDs from the list above
- Focus on generating comprehensive, realistic product lines for each producer
- Think like a real producer - what would they actually make and sell?

Note: Do NOT include certificationId - it will be added separately."""

        @retry(stop=stop_after_attempt(8), wait=wait_exponential(multiplier=2, min=2, max=60), retry=retry_if_exception_type(Exception))
        def generate_batch(existing_names, current_batch_size):
            prompt = build_prompt(existing_names, current_batch_size)
            try:
                response = self.client.beta.chat.completions.parse(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are generating creative but realistic farm producer data with their specialized products. Match products logically to producer types and assign allergens intelligently."},
                        {"role": "user", "content": prompt}
                    ],
                    response_format=ProducerBatch,
                    temperature=0.8
                )
                # Track token usage
                input_tokens = getattr(response.usage, 'prompt_tokens', 0)
                output_tokens = getattr(response.usage, 'completion_tokens', 0)
                batch_data = response.choices[0].message.parsed.producers
                batch_producers = [producer.model_dump() for producer in batch_data]
                batch_products = sum(len(producer["products"]) for producer in batch_producers)
                return {
                    "producers": batch_producers,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "batch_products": batch_products
                }
            except Exception as e:
                # If 429, raise to trigger retry
                if hasattr(e, 'status_code') and e.status_code == 429:
                    print("Rate limited (429). Retrying batch...")
                else:
                    print(f"Error in batch: {e}")
                raise

        def thread_task(args):
            idx, current_batch_size = args
            # For deduplication, pass last 5 names from global list (thread-safe)
            with lock:
                existing_names = [p["name"] for p in all_producers[-5:]]
            result = generate_batch(existing_names, current_batch_size)
            with lock:
                all_producers.extend(result["producers"])
                all_token_usage["input"] += result["input_tokens"]
                all_token_usage["output"] += result["output_tokens"]
                total_products_so_far = sum(len(p["products"]) for p in all_producers)
                print(f"[Thread {idx}] Generated batch of {len(result['producers'])} producers with {result['batch_products']} products. Total: {len(all_producers)} producers, {total_products_so_far} products")
                print(f"[Thread {idx}] 📊 Token usage - Input: {all_token_usage['input']:,}, Output: {all_token_usage['output']:,}, Total: {all_token_usage['input']+all_token_usage['output']:,}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            executor.map(thread_task, enumerate(batches))

        # Trim to exact count and add IDs and certifications
        producers = all_producers[:target_count]
        valid_allergen_ids = [allergen["allergenId"] for allergen in self.allergens]
        for producer in producers:
            producer["producerId"] = str(uuid.uuid4())
            producer["certificationId"] = random.choice(cert_ids)
            for product in producer["products"]:
                product["productId"] = str(uuid.uuid4())
                product["allergenIds"] = [aid for aid in product["allergenIds"] if aid in valid_allergen_ids]
        self.producers = producers
        # Update global token counters
        self.total_input_tokens += all_token_usage["input"]
        self.total_output_tokens += all_token_usage["output"]
        print(f"Successfully generated {len(producers)} producers with their products (parallel)")
        return producers
    
    def generate_stock(self) -> List[Dict[str, Any]]:
        """
        Generate stock data for all products from all producers.
        Each product gets exactly one stock record with random stock level.
        
        Returns:
            List of stock dictionaries
        """
        print("Generating stock records for all products...")
        
        if not self.producers:
            raise ValueError("Producers must be generated first")
        
        stock_records = []
        for producer in self.producers:
            producer_id = producer["producerId"]
            for product in producer["products"]:
                product_id = product["productId"]
                stock_record = {
                    "producerId": producer_id,
                    "productId": product_id,
                    "onStock": random.randint(0, 300)
                }
                stock_records.append(stock_record)
        
        if not stock_records:
            raise ValueError("No products found in any producers")
        
        print(f"Successfully generated {len(stock_records)} stock records (one for each product)")
        return stock_records
    
    def save_to_file(self, data: List[Dict[str, Any]], filename: str):
        """
        Save data to JSON file.
        
        Args:
            data: Data to save
            filename: Output filename
        """
        filepath = self.output_dir / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Saved {len(data)} records to {filepath}")
    
    def generate_all_data(self):
        """Generate all synthetic farm data."""
        print("Starting farm data generation...")
        
        try:
            # Generate allergens
            allergens = self.generate_allergens(100)
            self.save_to_file(allergens, "allergens.json")
            
            # Generate certifications
            certifications = self.generate_certifications(100)
            self.save_to_file(certifications, "certifications.json")
            
            # Generate producers with their products
            producers = self.generate_producers(200)
            self.save_to_file(producers, "producers.json")
            
            # Count total products across all producers
            total_products = sum(len(producer["products"]) for producer in producers)
            
            # Generate stock
            stock = self.generate_stock()
            self.save_to_file(stock, "stock.json")
            
            print("\n✅ All farm data generated successfully!")
            print(f"Files saved to: {self.output_dir.absolute()}")
            print(f"- allergens.json: {len(allergens)} records")
            print(f"- certifications.json: {len(certifications)} records")
            print(f"- producers.json: {len(producers)} records (with {total_products} products total)")
            print(f"- stock.json: {len(stock)} records")
            
            # Final token usage summary
            total_tokens = self.total_input_tokens + self.total_output_tokens
            print("\n📊 Final Token Usage Summary:")
            print(f"- Input tokens: {self.total_input_tokens:,}")
            print(f"- Output tokens: {self.total_output_tokens:,}")
            print(f"- Total tokens: {total_tokens:,}")
            
        except Exception as e:
            print(f"❌ Error during data generation: {e}")
            raise


def main():
    """Main function to run the data generation."""
    generator = FarmDataGenerator()
    generator.generate_all_data()


if __name__ == "__main__":
    main()