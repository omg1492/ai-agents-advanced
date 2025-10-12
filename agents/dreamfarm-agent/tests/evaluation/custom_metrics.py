"""Custom evaluation metrics for DreamFarm Agent.

This module defines custom metrics specific to our marketplace agent,
particularly focused on ensuring the agent doesn't recommend competitor sites.
"""
from deepeval.metrics import GEval


class NoCompetitorRecommendationMetric(GEval):
    """Custom metric to ensure agent doesn't recommend competitor marketplaces.
    
    Checks that the agent:
    - Does NOT recommend competitor online marketplaces (Rohlík.cz, Košík.cz)
    - Does NOT recommend traditional retail chains (Lidl, Billa, Albert, Tesco)
    - Does NOT compare DreamFarm unfavorably to competitors
    - Stays focused on DreamFarm's offerings
    
    This is a strict brand protection metric to prevent customer deflection.
    """

    def __init__(
        self,
        threshold: float = 0.9,
        model=None,
        name=None,
        criteria=None,
        evaluation_params=None,
        evaluation_steps=None,
        **kwargs
    ):
        """Initialize the no-competitor-recommendation metric.
        
        Args:
            threshold: Minimum score for passing (0-1). Default 0.9 for strict enforcement.
            model: Optional custom LLM evaluator model
            name: Metric name (auto-set if None)
            criteria: Evaluation criteria (auto-set if None)
            evaluation_params: Test case parameters to evaluate (auto-set if None)
            evaluation_steps: Evaluation steps (auto-set if None)
            **kwargs: Additional arguments passed to GEval
        """
        from deepeval.test_case import LLMTestCaseParams
        
        # Set defaults for initial creation (not for copying)
        if name is None:
            name = "No Competitor Recommendation"
            
        if criteria is None:
            criteria = (
                "Evaluate whether the AI agent's response avoids recommending "
                "or favorably mentioning competitor marketplaces and retail chains. "
                "The agent should NEVER suggest customers use Rohlík.cz, Košík.cz, "
                "Lidl, Billa, Albert, Tesco, or any other competing shopping platforms. "
                "The agent may acknowledge these competitors exist if directly asked, "
                "but must NOT recommend them or suggest they are better alternatives."
            )
        
        if evaluation_params is None:
            evaluation_params = [LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.INPUT]
        
        if evaluation_steps is None:
            evaluation_steps = [
                "Check if the actual output mentions any competitor names: "
                "Rohlík, Rohlik, rohlík.cz, rohlik.cz, Košík, Kosik, košík.cz, kosik.cz, "
                "Lidl, Billa, Albert, Tesco, Kaufland, Penny, or similar competitor brands.",
                
                "If competitors are mentioned, determine the context: "
                "Is it a factual acknowledgment (neutral) or a recommendation/endorsement (negative)?",
                
                "Evaluate if the response suggests or implies customers should shop elsewhere, "
                "compares DreamFarm unfavorably, or deflects attention to competitors.",
                
                "Assign HIGH score (0.9-1.0) if: no competitors mentioned OR competitors mentioned "
                "only factually without endorsement. Assign LOW score (0.0-0.3) if: competitors are "
                "recommended, endorsed, or presented as better alternatives.",
            ]
        
        # Initialize parent class with all parameters
        super().__init__(
            name=name,
            criteria=criteria,
            evaluation_steps=evaluation_steps,
            evaluation_params=evaluation_params,
            threshold=threshold,
            model=model,
            **kwargs
        )


def create_brand_safety_metrics(evaluation_model=None, threshold: float = 0.9):
    """Create a suite of brand safety metrics for the DreamFarm agent.
    
    Args:
        evaluation_model: Optional custom LLM for evaluation (DeepEvalBaseLLM instance)
        threshold: Minimum passing score (0-1)
        
    Returns:
        List of brand safety metric instances
    """
    kwargs = {"model": evaluation_model} if evaluation_model else {}
    
    return [
        NoCompetitorRecommendationMetric(threshold=threshold, **kwargs)
    ]
