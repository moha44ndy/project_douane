"""Compatibilite : delegue au pipeline RGI complet."""

from .rgi.pipeline import apply_rgi_pipeline_to_response

apply_rgi3b_to_response = apply_rgi_pipeline_to_response
evaluate_rgi3b = None  # deprecated; utiliser sam.rgi.RgiPipeline

__all__ = ["apply_rgi3b_to_response", "apply_rgi_pipeline_to_response"]
