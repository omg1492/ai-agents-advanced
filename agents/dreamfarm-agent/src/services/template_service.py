"""Template service for handling Jinja2 prompt templates."""

import logging
from pathlib import Path
from typing import Dict, Any

from jinja2 import Environment, FileSystemLoader, select_autoescape


logger = logging.getLogger(__name__)


class TemplateService:
    """Service for rendering Jinja2 templates for AI prompts.
    
    Manages prompt templates with proper escaping and context injection.
    """
    
    def __init__(self, template_dir: str = None):
        """Initialize the template service.
        
        Args:
            template_dir: Directory containing template files. 
                         Defaults to src/templates relative to this file.
        """
        if template_dir is None:
            # Default to templates directory relative to src/ (one level up from services/)
            current_dir = Path(__file__).parent  # src/services/
            template_dir = current_dir.parent / "templates"  # src/templates/
        
        self.template_dir = Path(template_dir)
        
        # Ensure template directory exists
        self.template_dir.mkdir(exist_ok=True)
        
        # Initialize Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        logger.info(f"Initialized template service with directory: {self.template_dir}")
    
    def render_template(self, template_name: str, context: Dict[str, Any] = None) -> str:
        """Render a template with the given context.
        
        Args:
            template_name: Name of the template file (with .j2 extension)
            context: Variables to pass to the template
            
        Returns:
            Rendered template as string
            
        Raises:
            FileNotFoundError: If template file doesn't exist
            jinja2.TemplateError: If template rendering fails
        """
        if context is None:
            context = {}
        
        try:
            template = self.env.get_template(template_name)
            rendered = template.render(**context)
            logger.debug(f"Successfully rendered template: {template_name}")
            return rendered
        except Exception as e:
            logger.error(f"Failed to render template {template_name}: {e}")
            raise
    
    def list_templates(self) -> list[str]:
        """List all available template files.
        
        Returns:
            List of template file names
        """
        template_files = []
        for file_path in self.template_dir.glob("*.j2"):
            template_files.append(file_path.name)
        return sorted(template_files)
    
    def template_exists(self, template_name: str) -> bool:
        """Check if a template file exists.
        
        Args:
            template_name: Name of the template file
            
        Returns:
            True if template exists, False otherwise
        """
        template_path = self.template_dir / template_name
        return template_path.exists()
