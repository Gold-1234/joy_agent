# in agent/session_data.py
from dataclasses import dataclass, field
from typing import Dict, Any

@dataclass
class SessionData:
    # Data we have at the start
    device_id: str
    is_new_user: bool
    child_profile: Dict[str, Any] = field(default_factory=dict)
    chat_history: list = field(default_factory=list)

    user_name: str | None = None
    age: int | None = None
    city: str | None = None
    interests: list[str] | None = None  
    dob: str | None = None            
    parent_mode: bool = False
    parental_instructions: Dict[str, Any] = field(default_factory=dict)
    preferences: Dict[str, Any] = field(default_factory=dict)
    personality: str | None = None
    last_messages: list = field(default_factory=list)