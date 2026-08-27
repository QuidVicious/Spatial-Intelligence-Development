"""
Prompt Engine: Formats and compiles physical lighting directives and domain 
syntheses into the final conditioning master string for the Synthesis Engine.
Enforces safety caps and clean sentence boundaries.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class CompiledPrompt:
    """Strongly typed output contract for the final synthesized prompt."""
    prompt: str
    target_provider: str
    target_model: str
    metadata: Dict[str, Any] = field(default_factory=dict)


def compile_conditioning(
    domain_result: Any, 
    lighting_state: Any, 
    target_provider: str = "GEMINI", 
    target_model: Optional[str] = None
) -> CompiledPrompt:
    
    doc_prompt = getattr(domain_result, "documentary_prompt", "")
    if not doc_prompt:
        doc_prompt = "Authentic architectural materials, planar structural rectification, and mature leafy vegetation."

    light_directive = getattr(lighting_state, "prompt_directive", "DEFAULT_DAYLIGHT")
    
    # Assemble master string
    final_prompt = (
        f"[LIGHTING & ATMOSPHERIC DIRECTIVE]\n"
        f"{light_directive}\n\n"
        f"[STRUCTURAL & MATERIAL SYNTHESIS]\n"
        f"{doc_prompt}"
    ).strip()
    
    # 2000 Character Cap Enforcement
    original_length = len(final_prompt)
    if original_length > 2000:
        header_len = len(f"[LIGHTING & ATMOSPHERIC DIRECTIVE]\n{light_directive}\n\n[STRUCTURAL & MATERIAL SYNTHESIS]\n")
        allowed_doc_len = 2000 - header_len - 1
        
        if allowed_doc_len > 0:
            sliced_doc = doc_prompt[:allowed_doc_len]
            last_period = sliced_doc.rfind(".")
            if last_period > 0:
                sliced_doc = sliced_doc[:last_period + 1]
            
            final_prompt = (
                f"[LIGHTING & ATMOSPHERIC DIRECTIVE]\n"
                f"{light_directive}\n\n"
                f"[STRUCTURAL & MATERIAL SYNTHESIS]\n"
                f"{sliced_doc}"
            ).strip()
        else:
            final_prompt = final_prompt[:1997] + "..."

    provider = target_provider.upper()
    model = target_model if target_model else ("marble-1.1-plus" if provider == "WORLD_LABS" else "gemini-3.1-flash-image")

    return CompiledPrompt(
        prompt=final_prompt,
        target_provider=provider,
        target_model=model,
        metadata={
            "original_char_count": original_length,
            "final_char_count": len(final_prompt),
            "was_edited": original_length > 2000,
            "includes_lighting": bool(light_directive)
        }
    )