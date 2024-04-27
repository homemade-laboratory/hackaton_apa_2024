import os
import ast
import json
import re


def parse_text_to_find_dict(text: str) -> str:
    parsed_text = re.findall(r'{([\s\S]+)}', text)
    if not parsed_text:
        parsed_text = "{}"
    else:
        parsed_text = parsed_text[0]
        parsed_text = "{" + parsed_text + "}"
    return parsed_text


def text_to_dict(text: str) -> dict:
    cleaned_text = text.strip()
    features_dict = ast.literal_eval(cleaned_text)
    return features_dict


def dict_to_json(feature_dict: dict) -> str:
    return json.dumps(feature_dict, indent=4, ensure_ascii=False)


def formatted_str(feature_dict: dict) -> str:
    feature_text = "{\n"
    for key, value in feature_dict.items():
        if not isinstance(value, (list, dict)):
            feature_text += f"    '{key}': '{value}',\n"
        else:
            feature_text += f"    '{key}': {value},\n"
    feature_text = feature_text[:-2]
    feature_text += "\n}"
    return feature_text


def delete_postfix(text: str) -> str:
    text_without_postfix = re.findall(r'(.+)_', text)[0]
    return text_without_postfix


def parse_key(text: str) -> str:
    text_key = re.findall(r"(.+):", text)[0]
    return text_key


def parse_value(text: str) -> str:
    text_value = re.findall(r": ([^:]+)$", text)[0]
    return text_value


def create_folders() -> None:
    dir_m = os.getcwd()
    input_path = os.path.join(dir_m, "input-pdfs")
    temp_path = os.path.join(dir_m, "temp")

    for folder in [input_path, temp_path]:
        if not os.path.exists(folder):
            os.makedirs(folder)


def main() -> None:
    pass


if __name__ == "__main__":
    main()
