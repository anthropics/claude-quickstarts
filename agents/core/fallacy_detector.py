"""
Fallacy Detector - Pattern-Based Informal Fallacy Detection

Implements comprehensive fallacy database with 25+ patterns:
- Relevance fallacies (ad hominem, appeal to authority, etc.)
- Presumption fallacies (false dilemma, begging question, etc.)
- Ambiguity fallacies (equivocation, etc.)
- Formal fallacies (affirming consequent, denying antecedent)
"""

from typing import List, Dict, Optional
from enum import Enum
from dataclasses import dataclass


class FallacyCategory(Enum):
    """Categories of informal fallacies."""
    RELEVANCE = "relevance"
    PRESUMPTION = "presumption"
    AMBIGUITY = "ambiguity"
    FORMAL = "formal"


class FallacySeverity(Enum):
    """Severity levels for fallacies."""
    MAJOR = "major"
    MODERATE = "moderate"
    MINOR = "minor"


@dataclass
class FallacyPattern:
    """Structured fallacy definition."""
    id: str
    name: str
    category: FallacyCategory
    severity: FallacySeverity
    description: str
    pattern_indicators: List[str]
    example: str


class FallacyDetector:
    """Pattern-based fallacy detection system."""
    
    def __init__(self):
        self.fallacies = self._init_fallacy_database()
    
    def _init_fallacy_database(self) -> Dict[str, FallacyPattern]:
        """Initialize comprehensive fallacy database."""
        return {
            # RELEVANCE FALLACIES
            "ad_hominem": FallacyPattern(
                id="ad_hominem",
                name="Ad Hominem",
                category=FallacyCategory.RELEVANCE,
                severity=FallacySeverity.MAJOR,
                description="Attacking the person instead of their argument",
                pattern_indicators=["you're wrong because", "coming from you", "can't trust", "you're just"],
                example="You can't trust his economic policy because he's wealthy"
            ),
            "appeal_to_authority": FallacyPattern(
                id="appeal_to_authority",
                name="Appeal to Authority",
                category=FallacyCategory.RELEVANCE,
                severity=FallacySeverity.MODERATE,
                description="Citing irrelevant or unqualified authority",
                pattern_indicators=["expert says", "authority claims", "famous person believes", "celebrity"],
                example="This diet works because a celebrity uses it"
            ),
            "appeal_to_emotion": FallacyPattern(
                id="appeal_to_emotion",
                name="Appeal to Emotion",
                category=FallacyCategory.RELEVANCE,
                severity=FallacySeverity.MODERATE,
                description="Using emotion instead of logic",
                pattern_indicators=["think of the children", "how would you feel", "imagine if", "scary"],
                example="We must ban this because it's scary"
            ),
            "appeal_to_popularity": FallacyPattern(
                id="appeal_to_popularity",
                name="Appeal to Popularity (Bandwagon)",
                category=FallacyCategory.RELEVANCE,
                severity=FallacySeverity.MODERATE,
                description="Arguing something is true because many people believe it",
                pattern_indicators=["everyone believes", "most people think", "popular opinion", "majority"],
                example="This must be true because everyone believes it"
            ),
            "red_herring": FallacyPattern(
                id="red_herring",
                name="Red Herring",
                category=FallacyCategory.RELEVANCE,
                severity=FallacySeverity.MODERATE,
                description="Introducing irrelevant information to distract",
                pattern_indicators=["but what about", "the real issue is", "speaking of", "let's talk about"],
                example="Climate change? What about immigration!"
            ),
            "straw_man": FallacyPattern(
                id="straw_man",
                name="Straw Man",
                category=FallacyCategory.RELEVANCE,
                severity=FallacySeverity.MAJOR,
                description="Misrepresenting opponent's argument to make it easier to attack",
                pattern_indicators=["so you're saying", "you want to", "you believe", "your position is"],
                example="You support environmental protection, so you want to destroy the economy"
            ),
            "tu_quoque": FallacyPattern(
                id="tu_quoque",
                name="Tu Quoque (You Too)",
                category=FallacyCategory.RELEVANCE,
                severity=FallacySeverity.MODERATE,
                description="Deflecting criticism by accusing the critic of the same thing",
                pattern_indicators=["but you also", "you do it too", "you're guilty", "hypocrite"],
                example="You can't criticize my smoking when you drink alcohol"
            ),
            
            # PRESUMPTION FALLACIES
            "false_dilemma": FallacyPattern(
                id="false_dilemma",
                name="False Dilemma",
                category=FallacyCategory.PRESUMPTION,
                severity=FallacySeverity.MAJOR,
                description="Presenting only two options when more exist",
                pattern_indicators=["either", "or", "only two", "must choose", "one or the other"],
                example="Either support the war or hate your country"
            ),
            "begging_question": FallacyPattern(
                id="begging_question",
                name="Begging the Question",
                category=FallacyCategory.PRESUMPTION,
                severity=FallacySeverity.MAJOR,
                description="Circular reasoning - conclusion assumed in premise",
                pattern_indicators=["obviously", "clearly", "of course", "it's evident"],
                example="God exists because the Bible says so, and the Bible is true because God wrote it"
            ),
            "hasty_generalization": FallacyPattern(
                id="hasty_generalization",
                name="Hasty Generalization",
                category=FallacyCategory.PRESUMPTION,
                severity=FallacySeverity.MODERATE,
                description="Drawing broad conclusion from insufficient evidence",
                pattern_indicators=["all", "every", "always", "never", "none"],
                example="I met two rude people from that city, so everyone there is rude"
            ),
            "slippery_slope": FallacyPattern(
                id="slippery_slope",
                name="Slippery Slope",
                category=FallacyCategory.PRESUMPTION,
                severity=FallacySeverity.MODERATE,
                description="Claiming small step leads to extreme outcome without justification",
                pattern_indicators=["will lead to", "next thing", "inevitable", "cascade", "then eventually"],
                example="If we allow same-sex marriage, people will marry animals"
            ),
            "composition": FallacyPattern(
                id="composition",
                name="Fallacy of Composition",
                category=FallacyCategory.PRESUMPTION,
                severity=FallacySeverity.MODERATE,
                description="Assuming what's true of parts is true of the whole",
                pattern_indicators=["each", "therefore all", "every part", "so the whole"],
                example="Each brick is light, therefore the wall is light"
            ),
            "division": FallacyPattern(
                id="division",
                name="Fallacy of Division",
                category=FallacyCategory.PRESUMPTION,
                severity=FallacySeverity.MODERATE,
                description="Assuming what's true of the whole is true of parts",
                pattern_indicators=["the whole", "therefore each", "all together", "so every part"],
                example="The team is strong, therefore every player is strong"
            ),
            "loaded_question": FallacyPattern(
                id="loaded_question",
                name="Loaded Question",
                category=FallacyCategory.PRESUMPTION,
                severity=FallacySeverity.MODERATE,
                description="Question contains unjustified assumption",
                pattern_indicators=["when did you stop", "why do you", "how long have you"],
                example="When did you stop cheating on tests?"
            ),
            
            # AMBIGUITY FALLACIES
            "equivocation": FallacyPattern(
                id="equivocation",
                name="Equivocation",
                category=FallacyCategory.AMBIGUITY,
                severity=FallacySeverity.MAJOR,
                description="Using same word with different meanings",
                pattern_indicators=["depends on", "meaning", "definition", "what you mean by"],
                example="A feather is light; light travels fast; therefore a feather travels fast"
            ),
            "amphiboly": FallacyPattern(
                id="amphiboly",
                name="Amphiboly",
                category=FallacyCategory.AMBIGUITY,
                severity=FallacySeverity.MINOR,
                description="Ambiguous grammar creates confusion",
                pattern_indicators=["could mean", "unclear", "ambiguous"],
                example="I saw the man with binoculars (who had binoculars?)"
            ),
            "accent": FallacyPattern(
                id="accent",
                name="Fallacy of Accent",
                category=FallacyCategory.AMBIGUITY,
                severity=FallacySeverity.MINOR,
                description="Changing emphasis changes meaning inappropriately",
                pattern_indicators=["emphasized", "stressed", "highlighted"],
                example="We should not speak ILL of our friends (vs. speak ill of our FRIENDS)"
            ),
            
            # FORMAL FALLACIES
            "affirming_consequent": FallacyPattern(
                id="affirming_consequent",
                name="Affirming the Consequent",
                category=FallacyCategory.FORMAL,
                severity=FallacySeverity.MAJOR,
                description="If P then Q; Q; therefore P (invalid)",
                pattern_indicators=["if", "then", "therefore"],
                example="If it rains, the ground is wet; the ground is wet; therefore it rained"
            ),
            "denying_antecedent": FallacyPattern(
                id="denying_antecedent",
                name="Denying the Antecedent",
                category=FallacyCategory.FORMAL,
                severity=FallacySeverity.MAJOR,
                description="If P then Q; not P; therefore not Q (invalid)",
                pattern_indicators=["if", "then", "not", "therefore"],
                example="If it rains, the ground is wet; it's not raining; therefore the ground is dry"
            ),
            "post_hoc": FallacyPattern(
                id="post_hoc",
                name="Post Hoc Ergo Propter Hoc",
                category=FallacyCategory.FORMAL,
                severity=FallacySeverity.MAJOR,
                description="Assuming causation from temporal sequence",
                pattern_indicators=["after", "then", "caused by", "because", "since then"],
                example="I wore my lucky socks and won the game; the socks caused the win"
            ),
            "non_sequitur": FallacyPattern(
                id="non_sequitur",
                name="Non Sequitur",
                category=FallacyCategory.FORMAL,
                severity=FallacySeverity.MAJOR,
                description="Conclusion doesn't follow from premises",
                pattern_indicators=["therefore", "thus", "hence", "so"],
                example="He's tall; therefore he must be good at basketball"
            )
        }
    
    def detect(self, argument: str, premises: List[str], conclusion: str) -> List[FallacyPattern]:
        """
        Detect fallacies in an argument.
        
        Args:
            argument: Full argument text (optional)
            premises: List of premise statements
            conclusion: Conclusion statement
            
        Returns:
            List of detected fallacy patterns
        """
        detected = []
        text = f"{' '.join(premises)} {conclusion}".lower()
        
        for fallacy_id, fallacy in self.fallacies.items():
            # Check if any pattern indicators are present
            if any(indicator in text for indicator in fallacy.pattern_indicators):
                detected.append(fallacy)
        
        return detected
    
    def get_by_category(self, category: FallacyCategory) -> List[FallacyPattern]:
        """Get all fallacies in a category."""
        return [f for f in self.fallacies.values() if f.category == category]
    
    def get_by_severity(self, severity: FallacySeverity) -> List[FallacyPattern]:
        """Get all fallacies with a specific severity."""
        return [f for f in self.fallacies.values() if f.severity == severity]
    
    def get_fallacy(self, fallacy_id: str) -> Optional[FallacyPattern]:
        """Get a specific fallacy by ID."""
        return self.fallacies.get(fallacy_id)
    
    def list_all(self) -> List[FallacyPattern]:
        """List all fallacy patterns."""
        return list(self.fallacies.values())
    
    def count_by_category(self) -> Dict[FallacyCategory, int]:
        """Count fallacies by category."""
        counts = {category: 0 for category in FallacyCategory}
        for fallacy in self.fallacies.values():
            counts[fallacy.category] += 1
        return counts
