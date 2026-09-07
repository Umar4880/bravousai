import re
from dataclasses import dataclass
from typing import Literal

@dataclass
class ContentQualityResult:
    score: float              # 0.0 - 1.0
    depth: Literal["rich", "adequate", "thin", "empty"]
    reason: str
    is_boilerplate: bool
    word_count: int
    sentence_count: int
    link_density: float       # ratio of link text to total text


def compute_link_density(text: str) -> float:
    """Ratio of URL/link content to total text."""
    if not text:
        return 0.0
    
    # Matches basic markdown links: [text](url)
    link_pattern = re.compile(r'\[([^\]]+)\]\([^\)]+\)')
    
    # Calculate the total length of the 'text' part of links
    link_text_len = sum(len(match.group(1)) for match in link_pattern.finditer(text))
    
    # Calculate length of raw URLs
    url_pattern = re.compile(r'https?://[^\s<>"]+|www\.[^\s<>"]+')
    url_len = sum(len(match.group(0)) for match in url_pattern.finditer(text))
    
    return min(1.0, (link_text_len + url_len) / max(1, len(text)))

def is_boilerplate(text: str) -> bool:
    """Detects nav menus, cookie banners, sidebar content via regex patterns."""
    if not text:
        return True
        
    lower_text = text.lower()
    
    patterns = [
        r"home\s*\|\s*about\s*\|\s*contact",
        r"accept\s+cookies",
        r"privacy\s+policy",
        r"back\s+to\s+top",
        r"subscribe\s+to\s+our\s+newsletter",
    ]
    
    for pattern in patterns:
        if re.search(pattern, lower_text):
            # If it has these patterns but is very long, it might be a real article that just has a footer.
            # So we only mark as boilerplate if it's relatively short or density is high.
            if len(text.split()) < 300:
                return True
                
    return False

def count_sentences(text: str) -> int:
    # A very simple sentence counter
    return max(0, len(re.split(r'[.!?]+', text)) - 1)

def classify_content_depth(word_count: int, link_density: float) -> Literal["rich", "adequate", "thin", "empty"]:
    """
    <50 words = empty
    50-150 words = thin  
    150-500 words = adequate
    >500 words with <40% link density = rich
    """
    if word_count < 50:
        return "empty"
    if word_count <= 150:
        return "thin"
    if word_count <= 500:
        return "adequate"
        
    if link_density < 0.4:
        return "rich"
    else:
        # High link density demotes the depth
        return "adequate"

def score_content_quality(text: str) -> ContentQualityResult:
    """Fast, deterministic content quality scoring."""
    if not text:
        return ContentQualityResult(0.0, "empty", "No text provided", True, 0, 0, 0.0)
        
    words = text.split()
    word_count = len(words)
    sentence_count = count_sentences(text)
    link_density = compute_link_density(text)
    boilerplate = is_boilerplate(text)
    
    depth = classify_content_depth(word_count, link_density)
    
    score = 1.0
    reason = "Looks good"
    
    if boilerplate:
        score *= 0.2
        reason = "Detected boilerplate patterns"
    
    if link_density > 0.4:
        score *= 0.5
        reason = f"High link density ({link_density:.2f})"
        
    if depth == "empty":
        score *= 0.1
        reason = "Content is practically empty"
    elif depth == "thin":
        score *= 0.4
        reason = "Content is thin"
    elif depth == "adequate":
        score *= 0.8
        
    if sentence_count < 3 and depth != "empty":
        score *= 0.5
        reason = "Very few sentences"
        
    return ContentQualityResult(
        score=score,
        depth=depth,
        reason=reason,
        is_boilerplate=boilerplate,
        word_count=word_count,
        sentence_count=sentence_count,
        link_density=link_density
    )

def pick_best_content(snippet: str, extracted: str) -> tuple[str, str]:
    """Compare snippet vs extracted, return (best_text, source_label)."""
    snippet_q = score_content_quality(snippet)
    extracted_q = score_content_quality(extracted)
    
    if extracted_q.score > snippet_q.score:
        return extracted, "extracted"
    elif snippet_q.score > extracted_q.score:
        return snippet, "snippet"
    else:
        # Tie-breaker: use whichever has more words, default to extracted if both are empty
        if extracted_q.word_count >= snippet_q.word_count:
            return extracted, "extracted"
        else:
            return snippet, "snippet"
