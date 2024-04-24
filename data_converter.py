import os
import ast
import json


def text_to_dict(text: str) -> dict:
    cleaned_text = text.strip()
    features_dict = ast.literal_eval(cleaned_text)
    return features_dict


def dict_to_json(feature_dict: dict) -> str:
    return json.dumps(feature_dict, indent=4, ensure_ascii=False)


def formatted_str(feature_dict: dict) -> str:
    feature_text = "{\n"
    for key, value in feature_dict.items():
        feature_text += f"    '{key}': '{value}',\n"
    feature_text = feature_text[:-2]
    feature_text += "\n}"
    return feature_text


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
