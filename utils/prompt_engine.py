import yaml
import re

def extract_vars_from_yaml(yaml_path):
    with open(yaml_path, "r", encoding="utf-8") as f:
        yml = yaml.safe_load(f)
    prompt = yml["prompt"]
    # Find all {{var}} in prompt
    return list(set(re.findall(r"\{\{(\w+)\}\}", prompt)))

def build_prompt_from_yaml(yaml_path, user_vars, sys_vars=None):
    if sys_vars is None:
        sys_vars = {}
    with open(yaml_path, "r", encoding="utf-8") as f:
        yml = yaml.safe_load(f)
    prompt = yml["prompt"]
    vars_all = {**sys_vars, **user_vars}
    for k, v in vars_all.items():
        prompt = prompt.replace(f"{{{{{k}}}}}", str(v))
    return prompt
