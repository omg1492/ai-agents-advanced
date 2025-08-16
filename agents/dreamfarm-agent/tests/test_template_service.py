"""Tests for the template service."""

import pytest
from pathlib import Path
import tempfile

from src.services.template_service import TemplateService


pytestmark = pytest.mark.unit


class TestTemplateService:
    """Test cases for TemplateService."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Create temporary directory for templates
        self.temp_dir = tempfile.mkdtemp()
        self.template_service = TemplateService(template_dir=self.temp_dir)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        # Clean up temp directory
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_render_simple_template(self):
        """Test rendering a simple template."""
        # Create test template
        template_content = "Hello {{ name }}!"
        template_path = Path(self.temp_dir) / "test.j2"
        template_path.write_text(template_content)
        
        # Render template
        result = self.template_service.render_template("test.j2", {"name": "World"})
        
        assert result == "Hello World!"
    
    def test_render_template_with_complex_context(self):
        """Test rendering template with complex context."""
        # Create test template
        template_content = """
        User: {{ user.name }}
        Products:
        {% for product in products -%}
        - {{ product.name }}: ${{ product.price }}
        {% endfor %}
        """
        template_path = Path(self.temp_dir) / "complex.j2"
        template_path.write_text(template_content)
        
        # Render template
        context = {
            "user": {"name": "John"},
            "products": [
                {"name": "Apples", "price": "3.50"},
                {"name": "Carrots", "price": "2.00"}
            ]
        }
        result = self.template_service.render_template("complex.j2", context)
        
        assert "User: John" in result
        assert "- Apples: $3.50" in result
        assert "- Carrots: $2.00" in result
    
    def test_render_template_not_found(self):
        """Test error handling for missing template."""
        with pytest.raises(Exception):  # Should raise TemplateNotFound
            self.template_service.render_template("nonexistent.j2")
    
    def test_list_templates(self):
        """Test listing available templates."""
        # Create test templates
        (Path(self.temp_dir) / "template1.j2").write_text("Template 1")
        (Path(self.temp_dir) / "template2.j2").write_text("Template 2")
        (Path(self.temp_dir) / "not_template.txt").write_text("Not a template")
        
        templates = self.template_service.list_templates()
        
        assert "template1.j2" in templates
        assert "template2.j2" in templates
        assert "not_template.txt" not in templates
        assert len(templates) == 2
    
    def test_template_exists(self):
        """Test checking if template exists."""
        # Create test template
        template_path = Path(self.temp_dir) / "exists.j2"
        template_path.write_text("Template content")
        
        assert self.template_service.template_exists("exists.j2")
        assert not self.template_service.template_exists("doesnt_exist.j2")
    
    def test_render_with_empty_context(self):
        """Test rendering template with no context."""
        # Create test template
        template_content = "Static content only"
        template_path = Path(self.temp_dir) / "static.j2"
        template_path.write_text(template_content)
        
        result = self.template_service.render_template("static.j2")
        
        assert result == "Static content only"
