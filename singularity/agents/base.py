"""
Singularity — Základní datové typy agentů.
Identické s Omega; zachováno pro kompatibilitu.
"""
from dataclasses import dataclass, field
from enum import Enum


class AgentRole(str, Enum):
    RESEARCHER   = "badatel"
    PROGRAMMER   = "programátor"
    CRITIC       = "kritik"
    PLANNER      = "plánovač"
    COMMUNICATOR = "komunikátor"


@dataclass
class AgentOutput:
    role:              AgentRole
    content:           str
    confidence:        float          # 0.0 – 1.0
    risk_score:        float          # 0.0 – 1.0
    requires_approval: bool
    provider_used:     str = "unknown"   # "claude" | "gemini"
    metadata:          dict = field(default_factory=dict)
