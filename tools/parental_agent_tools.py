from typing import Dict
from livekit.agents import function_tool, RunContext
from tools.supabase_tools import SupabaseHelper
import logging
from datetime import datetime
import asyncio

logger = logging.getLogger("livekit.parental_tools")

def create_set_parental_rules_tool():
    schema = {
        "type": "function",
        "name": "set_parental_rules",
        "description": "Update one or more parental rules for a child's profile.",
        "parameters": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "Text identifier of the child profile to update"
                },
                "rules": {
                    "type": "object",
                    "properties": {
                        "language_filter": {
                            "type": "boolean",
                            "description": "Enable/disable language filter"
                        },
                        "bedtime_reminder": {
                            "type": "boolean",
                            "description": "Enable/disable bedtime reminder"
                        },
                        "bedtime": {
                            "type": "string",
                            "description": "Set bedtime in HH:MM AM/PM format (e.g., '8:00 PM')"
                        },
                        "restricted_topics": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "description": "A restricted conversation topic"
                            },
                            "description": "List of restricted conversation topics"
                        },
                        "tts_pitch_preference": {
                            "type": "string",
                            "description": "Text-to-speech pitch preference (e.g., 'low', 'medium', 'high')"
                        },
                        "learning_focus": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "description": "An educational topic to focus on"
                            },
                            "description": "List of educational topics to emphasize"
                        },
                        "alert_on_restricted": {
                            "type": "boolean",
                            "description": "Enable/disable alerts for restricted topics"
                        }
                    },
                    "additionalProperties": False
                }
            },
            "required": ["device_id", "rules"]
        }
    }

    async def handler(raw_arguments: Dict[str, object], context: RunContext) -> str:
        try:
            device_id = raw_arguments["device_id"]
            rules = raw_arguments["rules"]

            if not isinstance(device_id, str) or not device_id:
                raise ValueError("device_id must be a non-empty string")
            if not isinstance(rules, dict):
                raise ValueError("rules must be an object")

            valid_fields = {
                "language_filter": bool,
                "bedtime_reminder": bool,
                "bedtime": str,
                "restricted_topics": list,
                "tts_pitch_preference": str,
                "learning_focus": list,
                "alert_on_restricted": bool
            }
            update_data = {}
            for field, value in rules.items():
                if field not in valid_fields:
                    raise ValueError(f"Invalid field: {field}")
                if not isinstance(value, valid_fields[field]):
                    raise ValueError(f"Invalid type for {field}: expected {valid_fields[field].__name__}")
                if field == "bedtime" and value:
                    try:
                        datetime.strptime(value, "%I:%M %p")
                        # Convert to HH:MM:SS for TIME column
                        update_data[field] = datetime.strptime(value, "%I:%M %p").strftime("%H:%M:%S")
                    except ValueError:
                        raise ValueError(f"Invalid bedtime format: {value}. Use 'HH:MM AM/PM' (e.g., '9:00 PM').")
                elif field in ("restricted_topics", "learning_focus"):
                    for item in value:
                        if not isinstance(item, str):
                            raise ValueError(f"All items in {field} must be strings")
                    update_data[field] = value
                else:
                    update_data[field] = value

            supabase = SupabaseHelper()
            result = await supabase.update_parental_rule(device_id, update_data)
            if result:
                updated_fields = ", ".join(f"{k}={v}" for k, v in update_data.items())
                logger.info(f"Successfully updated parental rules for device_id {device_id}: {updated_fields}")
                return f"Updated parental rules for device_id {device_id}: {updated_fields}"
            else:
                logger.error(f"Failed to update parental rules for device_id {device_id}")
                return f"Failed to update parental rules for device_id {device_id}"
        except Exception as e:
            logger.error(f"Error in set_parental_rules handler: {e}, raw_arguments={raw_arguments}")
            return f"Sorry, I couldn't update parental rules. Please try again."

    return function_tool(handler, raw_schema=schema)

def create_parental_tool(field: str, field_type: str):
    parameters = {
        "type": "object",
        "properties": {
            "device_id": {
                "type": "string",
                "description": "Text identifier of the child profile to update"
            },
            "value": {
                "type": field_type,
                "description": f"New value for {field}"
            },
        },
        "required": ["device_id", "value"],
    }
    if field_type == "array":
        parameters["properties"]["value"]["items"] = {
            "type": "string",
            "description": f"Individual item for {field}"
        }

    schema = {
        "type": "function",
        "name": f"set_{field}",
        "description": f"Update the `{field}` field in parental_rules.",
        "parameters": parameters,
    }

    async def handler(raw_arguments: Dict[str, object], context: RunContext) -> str:
        try:
            device_id = raw_arguments["device_id"]
            value = raw_arguments["value"]
            if not isinstance(device_id, str) or not device_id:
                raise ValueError("device_id must be a non-empty string")
            if field_type == "boolean" and not isinstance(value, bool):
                raise ValueError(f"{field} must be a boolean")
            if field_type == "string" and not isinstance(value, str):
                raise ValueError(f"{field} must be a string")
            if field_type == "array" and not isinstance(value, list):
                raise ValueError(f"{field} must be a list of strings")
            if field_type == "array":
                for item in value:
                    if not isinstance(item, str):
                        raise ValueError(f"All items in {field} must be strings")
            if field == "bedtime" and value:
                try:
                    datetime.strptime(value, "%I:%M %p")
                    # Convert to HH:MM:SS for TIME column
                    value = datetime.strptime(value, "%I:%M %p").strftime("%H:%M:%S")
                except ValueError:
                    raise ValueError(f"Invalid bedtime format: {value}. Use 'HH:MM AM/PM' (e.g., '9:00 PM').")

            supabase = SupabaseHelper()
            result = await supabase.update_parental_rule(device_id, {field: value})
            if result:
                logger.info(f"Updated {field} to {value} for device_id {device_id}")
                return f"Updated {field} to {value} for device_id {device_id}"
            else:
                logger.error(f"Failed to update {field} for device_id {device_id}")
                return f"Failed to update {field} for device_id {device_id}"
        except Exception as e:
            logger.error(f"Error in set_{field} handler: {e}, raw_arguments={raw_arguments}")
            return f"Sorry, I couldn't update {field}. Please try again."

    return function_tool(handler, raw_schema=schema)

PARENTAL_RULE_TOOLS = [
    create_set_parental_rules_tool(),
    create_parental_tool("language_filter", "boolean"),
    create_parental_tool("bedtime_reminder", "boolean"),
    create_parental_tool("bedtime", "string"),
    create_parental_tool("restricted_topics", "array"),
    create_parental_tool("tts_pitch_preference", "string"),
    create_parental_tool("learning_focus", "array"),
    create_parental_tool("alert_on_restricted", "boolean"),
]