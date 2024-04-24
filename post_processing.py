from openai import OpenAI
from config import API_KEY

client = OpenAI(api_key=API_KEY)


def generate_response(text: str) -> str:
    completion = client.chat.completions.create(model="gpt-3.5-turbo",
    messages=[{"role": "system", "content": "You are a helpful assistant."},
              {"role": "user", "content": "Попробуй извлечь фичи товара из этого текста, текст был распознан "
                                          "OCR, некоторые символы могли быть повреждены или пропущены, попробуй "
                                          "их восстановить. "
                                          "Представь ответ ввиде dict python {'фича': 'значение'}. "
                                          "Не должно быть вложенных словарей и списков. "
                                          "Избегай юридической информации, оставь только технические "
                                          "характеристики, а также пропускай данные в которых неуверен. "
                                          "Если текст сложный и ничего не удается распознать, верни пустой словарь {}"},
              {"role": "assistant", "content": "Конечно, пришли текст, и я постараюсь извлечь фичи товара."},
              {"role": "user", "content": text}
              ])
    return completion.choices[0].message.content


def main() -> None:
    pass


if __name__ == "__main__":
    main()