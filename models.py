"""
Pydantic modely pro strukturované výstupy z Claude API.
Fáze 1: Nahrazení regex parsování strukturovanými výstupy (tool_use).
"""

from pydantic import BaseModel, Field
from typing import List


class Topic(BaseModel):
    """Jedno téma z analýzy herních článků."""
    topic: str = Field(description="Název tématu")
    title: str = Field(description="Navržený český titulek článku")
    angle: str = Field(description="Úhel pohledu - jak téma uchopit")
    context: str = Field(description="2-3 věty kontextu s konkrétními fakty")
    hook: str = Field(description="Hlavní hook pro banner - úderná věta nebo číslo")
    visual: str = Field(description="Vizuální návrh pro banner")
    virality_score: int = Field(ge=1, le=100, description="Hodnocení virality 1-100")
    why_now: str = Field(description="Proč je to aktuální")
    sources: List[str] = Field(description="URL zdrojových článků")
    seo_keywords: str = Field(description="SEO klíčová slova oddělená čárkou")
    game_name: str = Field(default="N/A", description="Anglický název hlavní hry, nebo N/A")


class AnalysisResult(BaseModel):
    """Výsledek analýzy herních článků od Claude."""
    topics: List[Topic] = Field(description="TOP témata seřazená od nejdůležitějšího")
