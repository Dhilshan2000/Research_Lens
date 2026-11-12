from enum import Enum, auto
from typing import Callable, Dict, Any, Optional
import logging

logger = logging.getLogger("ResearchLens.ScraperStateMachine")


class CrawlState(str, Enum):
    IDLE = "IDLE"
    INITIALIZING = "INITIALIZING"
    DISCOVERING = "DISCOVERING"
    FILTERING = "FILTERING"
    EXTRACTING = "EXTRACTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ScrapingStateMachine:
    """State machine governing the multi-phase crawling and discovery process:
    IDLE -> INITIALIZING -> DISCOVERING -> FILTERING -> EXTRACTING -> COMPLETED
    """

    def __init__(self, on_state_change: Optional[Callable[[CrawlState, Dict[str, Any]], None]] = None):
        self.state = CrawlState.IDLE
        self.context: Dict[str, Any] = {}
        self.history = [CrawlState.IDLE]
        self.on_state_change = on_state_change

    def transition_to(self, new_state: CrawlState, payload: Optional[Dict[str, Any]] = None):
        old_state = self.state
        self.state = new_state
        self.history.append(new_state)
        if payload:
            self.context.update(payload)
        logger.info(f"StateMachine transitioned: {old_state.value} -> {new_state.value}")
        if self.on_state_change:
            try:
                self.on_state_change(new_state, self.context)
            except Exception as e:
                logger.warning(f"Error in on_state_change callback: {e}")

    def fail(self, reason: str):
        self.context["error"] = reason
        self.transition_to(CrawlState.FAILED, {"error": reason})

    def is_terminal(self) -> bool:
        return self.state in [CrawlState.COMPLETED, CrawlState.FAILED]

