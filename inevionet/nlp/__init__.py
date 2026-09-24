"""InevioNet NLP - рекурсивный конвейер для агентов.

P98: НЛП-конвейер для спор, разведчиков и рефрейминга ситуаций.
"""
from .pipeline import (
    run_pipeline, STAGES, STAGE_NAMES, ENABLE_STAGES, STAGE_PRIORITY,
    extract_outputs, spore_analyze_node, node_to_situation,
    validate_input,
)

__all__ = [
    "run_pipeline", "STAGES", "STAGE_NAMES", "ENABLE_STAGES", "STAGE_PRIORITY",
    "extract_outputs", "spore_analyze_node", "node_to_situation",
    "validate_input",
]
