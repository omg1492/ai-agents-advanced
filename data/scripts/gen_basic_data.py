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
    products: List[Product] = Field(..., description="List of 0-10 products that this producer makes, logically matching their specialization")


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
                
                batch_data = response.choices[0].message.parsed.allergens
                batch_allergens = [allergen.model_dump() for allergen in batch_data]
                allergens.extend(batch_allergens)
                print(f"Generated batch of {len(batch_allergens)} allergens. Total: {len(allergens)}")
                
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
                
                batch_data = response.choices[0].message.parsed.certifications
                batch_certifications = [cert.model_dump() for cert in batch_data]
                certifications.extend(batch_certifications)
                print(f"Generated batch of {len(batch_certifications)} certifications. Total: {len(certifications)}")
                
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
        Generate producer data with valid certification IDs and their products using structured outputs.
        
        Args:
            target_count: Number of producers to generate
            
        Returns:
            List of producer dictionaries
        """
        print(f"Generating {target_count} producers with their products...")
        
        if not self.certifications or not self.allergens:
            raise ValueError("Certifications and allergens must be generated first")
        
        cert_ids = [cert["certificationId"] for cert in self.certifications]
        
        # Prepare allergen information for the LLM
        allergen_info = []
        for allergen in self.allergens:
            allergen_info.append({
                "id": allergen["allergenId"],
                "name": allergen["name"],
                "description": allergen["description"]
            })
        
        allergen_context = "Available allergens for product assignment:\n"
        for allergen in allergen_info:
            allergen_context += f"- ID: {allergen['id']}, Name: {allergen['name']}, Description: {allergen['description']}\n"
        
        producers = []
        batch_size = 5  # Smaller batches due to complex nested structure
        
        while len(producers) < target_count:
            remaining = target_count - len(producers)
            current_batch_size = min(batch_size, remaining)
            
            existing_context = ""
            if producers:
                existing_names = [p["name"] for p in producers[-5:]]
                existing_context = f"Already generated producers (avoid duplicates): {', '.join(existing_names)}\n\n"
            
            prompt = f"""{existing_context}{allergen_context}

Generate {current_batch_size} different farm product producers with their products. 
Include various types: family farms, cooperatives, organic producers, specialty farms, etc.
Make them diverse in location, size, and specialization. Be creative and sometimes funny with names.

Each producer should have:
- name: Creative, realistic producer/farm name
- description: Detailed description of the producer, their history, specialization, and philosophy
- products: List of 0-20 products that this producer makes (should logically match their specialization)

For each product within a producer:
- name: Creative, appetizing product name that fits the producer's specialization
- description: Detailed description including taste, uses, origin story, or fun facts
- allergenIds: List of allergen IDs that logically apply to this product (0-5 allergens)

IMPORTANT: 
- Products should match the producer's specialization (dairy farm → dairy products, etc.)
- Choose allergens intelligently based on product type
- Use actual allergen IDs from the list above
- Some producers might have 0 products if they're just starting or in transition

Note: Do NOT include certificationId - it will be added separately."""
            
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
                
                # Handle potential refusal
                if response.choices[0].message.refusal:
                    print(f"Model refused to generate producers: {response.choices[0].message.refusal}")
                    continue
                
                batch_data = response.choices[0].message.parsed.producers
                batch_producers = [producer.model_dump() for producer in batch_data]
                producers.extend(batch_producers)
                print(f"Generated batch of {len(batch_producers)} producers. Total: {len(producers)}")
                
            except Exception as e:
                print(f"Error generating producers batch: {e}")
                continue
        
        # Trim to exact count and add IDs and certifications
        producers = producers[:target_count]
        valid_allergen_ids = [allergen["allergenId"] for allergen in self.allergens]
        
        for producer in producers:
            producer["producerId"] = str(uuid.uuid4())
            producer["certificationId"] = random.choice(cert_ids)
            
            # Add product IDs and validate allergen IDs
            for product in producer["products"]:
                product["productId"] = str(uuid.uuid4())
                # Validate that allergen IDs are valid
                product["allergenIds"] = [aid for aid in product["allergenIds"] if aid in valid_allergen_ids]
        
        self.producers = producers
        print(f"Successfully generated {len(producers)} producers with their products")
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
            
        except Exception as e:
            print(f"❌ Error during data generation: {e}")
            raise


def main():
    """Main function to run the data generation."""
    generator = FarmDataGenerator()
    generator.generate_all_data()


if __name__ == "__main__":
    main()