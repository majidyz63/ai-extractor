import os

def get_model_info(model):
    # Simple: all OpenRouter models, use same endpoint
    return {
        "name": model,
        "endpoint": "https://openrouter.ai/api/v1/chat/completions"
    }
