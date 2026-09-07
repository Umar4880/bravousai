from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class LayoutSignals:
    score: int
    tier: str  # "tier1_chat", "tier2_download", "tier3_inline_card"
    layout_hint: str


class LayoutSignalsScanner:
    """
    Zero-LLM scanner that analyzes synthesis output and determines the optimal
    presentation tier and layout hint.
    """

    # Thresholds
    TIER3_SCORE_THRESHOLD = 6
    TIER2_SCORE_THRESHOLD = 4
    WORD_COUNT_TIER2_THRESHOLD = 1500

    @classmethod
    def scan(cls, synthesis: str, data_points: list[dict[str, Any]], user_query: str = "") -> LayoutSignals:
        score = 0
        synthesis = synthesis or ""
        
        # Calculate base metrics
        word_count = len(synthesis.split())
        data_points_count = len(data_points)
        
        # 1. Data Points
        if data_points_count >= 3:
            score += 3
            
        # 2. Numeric Density
        if word_count > 0:
            numeric_words = len(re.findall(r'\b\d+(?:\.\d+)?%?\b', synthesis))
            numeric_density = numeric_words / word_count
            if numeric_density > 0.08:
                score += 2

        # 3. Tables
        table_matches = re.findall(r'\|.*\|.*\n\|[-:\s|]+\|', synthesis)
        if len(table_matches) >= 1:
            score += 2

        # 4. Causal Chains
        # Look for phrases like A -> B -> C or A → B → C
        chain_matches = re.findall(r'(?:->|→)[^->→]+(?:->|→)', synthesis)
        if len(chain_matches) >= 1:
            score += 2
            
        # 5. Comparative Entities (very rough heuristic)
        if re.search(r'\b(compare|vs|versus|difference)\b', user_query, re.IGNORECASE):
            score += 2

        # 6. Dates and Events
        date_matches = re.findall(r'\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},?\s+\d{4}\b', synthesis)
        if len(date_matches) >= 4:
            score += 1
            
        # 7. Word Count
        if word_count > 1200:
            score += 1

        # 8. Code Blocks
        code_blocks = re.findall(r'```', synthesis)
        if len(code_blocks) >= 2: # Pairs of ```
            score += 3
            
        # 9. Markdown Headers
        headers = re.findall(r'^#{1,6}\s', synthesis, re.MULTILINE)
        if len(headers) >= 5:
            score += 1

        # Determine Tier
        tier = "tier1_chat"
        layout_hint = "hybrid_article"

        if score >= cls.TIER3_SCORE_THRESHOLD and data_points_count >= 3:
            tier = "tier3_inline_card"
            layout_hint = "research_dashboard" if data_points_count >= 6 else "hybrid_article"
        elif score >= cls.TIER2_SCORE_THRESHOLD or word_count > cls.WORD_COUNT_TIER2_THRESHOLD:
            tier = "tier2_download"
            layout_hint = "plan_document" if "plan" in user_query.lower() else "hybrid_article"
            
        return LayoutSignals(score=score, tier=tier, layout_hint=layout_hint)
