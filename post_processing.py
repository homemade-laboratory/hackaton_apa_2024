from openai import OpenAI

from data_converter import text_to_dict, formatted_str, parse_text_to_find_dict
from config import API_KEY


client = OpenAI(api_key=API_KEY)
model = "gpt-3.5-turbo"


def generate_response(text: str) -> str:
    cleaned_text = clean_text(text)
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {
                "role": "user", "content": "Попробуй извлечь фичи товара из этого текста, текст был распознан "
                                           "OCR, некоторые символы могли быть повреждены или пропущены, попробуй "
                                           "их восстановить. "
                                           "Представь ответ ввиде dict python {'фича': 'значение'}. "
                                           "Не должно быть вложенных словарей и списков. "
                                           "Избегай юридической информации, оставь только технические "
                                           "характеристики, а также пропускай данные в которых не уверен. "
                                           f"{cleaned_text}"
            },
        ]
    )
    parsed_text = parse_text_to_find_dict(completion.choices[0].message.content)
    feature_text = formatted_str(text_to_dict(parsed_text))
    return feature_text


def make_direct_prompt(text: str, cleaned_text: str, messages_history: list) -> str:
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {
                "role": "user", "content": "Попробуй извлечь фичи товара из этого текста, текст был распознан "
                                           "OCR, некоторые символы могли быть повреждены или пропущены, попробуй "
                                           "их восстановить. "
                                           "Представь ответ ввиде dict python {'фича': 'значение'}. "
                                           "Не должно быть вложенных словарей и списков. "
                                           "Избегай юридической информации, оставь только технические "
                                           "характеристики, а также пропускай данные в которых не уверен. "
                                           f"{cleaned_text}"
            },
        ] + messages_history
    )
    print(completion.choices[0].message.content)
    parsed_text = parse_text_to_find_dict(completion.choices[0].message.content)
    feature_text = formatted_str(text_to_dict(parsed_text))
    return feature_text, completion.choices[0].message.content


def compare_features(ftext_1: str, ftext_2: str) -> str:
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {
                "role": "user", "content": "У меня есть набор фичей, полученный из технических паспортов двух товаров. "
                                           "Нужно найти общие характеристики среди их свойств и вывести в формате:\n"
                                           "Свойство | Характеристика первого товара | Характеристика второго товара\n"
                                           "Если ты видишь, что ключи немного отличаются, но смысл характеристик "
                                           "одинаковый, старайся включать их в ответ. Ты можешь также немного "
                                           "преобразовать как ключи, так и значения фичей, чтобы привести их к одному, "
                                           "удобно сравнимому виду. Приведи в ответе только те фичи, которые есть у "
                                           "обоих товаров. Если характеристика есть только у одного, то пропускай ее. "
                                           f"{ftext_1}\n{ftext_2}."
            },
        ]
    )
    return completion.choices[0].message.content


def clean_text(text:str) -> str:
    cleaned_text = text.replace("'", '"')
    return cleaned_text


def main() -> None:
    pass


if __name__ == "__main__":
    main()
