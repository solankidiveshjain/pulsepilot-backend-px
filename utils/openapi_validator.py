"""
OpenAPI documentation validation and alignment
"""

import json
from typing import Dict, Any, List
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from utils.structured_logging import get_structured_logger

logger = get_structured_logger(__name__)


class OpenAPIValidator:
    """Validator for OpenAPI documentation alignment"""
    
    def __init__(self, app: FastAPI):
        """
        Initialize OpenAPI validator
        
        Args:
            app: FastAPI application instance
        """
        self.app = app
    
    def validate_openapi_spec(self) -> Dict[str, Any]:
        """
        Validate OpenAPI specification alignment
        
        Returns:
            Validation results
        """
        openapi_schema = get_openapi(
            title=self.app.title,
            version=self.app.version,
            description=self.app.description,
            routes=self.app.routes,
        )
        
        validation_results = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "endpoint_count": 0,
            "model_count": 0
        }
        
        try:
            # Validate paths
            paths = openapi_schema.get("paths", {})
            validation_results["endpoint_count"] = len(paths)
            
            for path, methods in paths.items():
                for method, spec in methods.items():
                    if method.upper() in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                        self._validate_endpoint_spec(path, method, spec, validation_results)
            
            # Validate components/schemas
            components = openapi_schema.get("components", {})
            schemas = components.get("schemas", {})
            validation_results["model_count"] = len(schemas)
            
            for schema_name, schema_spec in schemas.items():
                self._validate_schema_spec(schema_name, schema_spec, validation_results)
            
            logger.info("OpenAPI validation completed",
                       endpoint_count=validation_results["endpoint_count"],
                       model_count=validation_results["model_count"],
                       errors=len(validation_results["errors"]),
                       warnings=len(validation_results["warnings"]))
            
        except Exception as e:
            validation_results["valid"] = False
            validation_results["errors"].append(f"Validation failed: {str(e)}")
            logger.error("OpenAPI validation failed", error=str(e))
        
        return validation_results
    
    def _validate_endpoint_spec(
        self,
        path: str,
        method: str,
        spec: Dict[str, Any],
        results: Dict[str, Any]
    ) -> None:
        """
        Validate individual endpoint specification
        
        Args:
            path: API path
            method: HTTP method
            spec: Endpoint specification
            results: Validation results to update
        """
        # Check required fields
        if "summary" not in spec:
            results["warnings"].append(f"{method.upper()} {path}: Missing summary")
        
        if "description" not in spec:
            results["warnings"].append(f"{method.upper()} {path}: Missing description")
        
        # Check response schemas
        responses = spec.get("responses", {})
        if not responses:
            results["errors"].append(f"{method.upper()} {path}: No responses defined")
        
        # Check for 200/201 success responses
        success_codes = ["200", "201"]
        has_success = any(code in responses for code in success_codes)
        if not has_success and method.upper() != "DELETE":
            results["warnings"].append(f"{method.upper()} {path}: No success response defined")
        
        # Check for error responses
        error_codes = ["400", "401", "403", "404", "422", "500"]
        has_error = any(code in responses for code in error_codes)
        if not has_error:
            results["warnings"].append(f"{method.upper()} {path}: No error responses defined")
    
    def _validate_schema_spec(
        self,
        schema_name: str,
        schema_spec: Dict[str, Any],
        results: Dict[str, Any]
    ) -> None:
        """
        Validate schema specification
        
        Args:
            schema_name: Schema name
            schema_spec: Schema specification
            results: Validation results to update
        """
        # Check for required properties
        if "properties" not in schema_spec:
            results["warnings"].append(f"Schema {schema_name}: No properties defined")
        
        # Check for descriptions
        if "description" not in schema_spec:
            results["warnings"].append(f"Schema {schema_name}: Missing description")
        
        # Check property descriptions
        properties = schema_spec.get("properties", {})
        for prop_name, prop_spec in properties.items():
            if "description" not in prop_spec:
                results["warnings"].append(f"Schema {schema_name}.{prop_name}: Missing description")
    
    def generate_spec_file(self, output_path: str = "openapi.json") -> None:
        """
        Generate OpenAPI specification file
        
        Args:
            output_path: Output file path
        """
        openapi_schema = get_openapi(
            title=self.app.title,
            version=self.app.version,
            description=self.app.description,
            routes=self.app.routes,
        )
        
        with open(output_path, "w") as f:
            json.dump(openapi_schema, f, indent=2)
        
        logger.info("OpenAPI specification generated", file=output_path)


def validate_openapi_alignment(app: FastAPI) -> Dict[str, Any]:
    """
    Validate OpenAPI documentation alignment
    
    Args:
        app: FastAPI application
        
    Returns:
        Validation results
    """
    validator = OpenAPIValidator(app)
    return validator.validate_openapi_spec()
