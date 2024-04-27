import logging
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    PicklePersistence,
    filters,
)
from io import BytesIO

from ocr import extract_text
from post_processing import compare_features, generate_response, make_direct_prompt
from data_converter import (
    create_folders,
    delete_postfix,
    dict_to_json,
    formatted_str,
    parse_key,
    parse_value,
    text_to_dict,
)
from config import TOKEN


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 4096  # no more than 4096
NUMBER_OF_ATTEMPTS = 5

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_text(
        "Привет, {}! Отправь мне PDF-файл, и я постараюсь его прочитать.".format(user.first_name)
    )


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    document = update.message.document
    create_folders()
    if document.mime_type == 'application/pdf':
        file = await context.bot.get_file(document.file_id)
        await file.download_to_drive("input-pdfs/{}".format(document.file_name))
        await update.message.reply_text("PDF-файл успешно скачан! Идет обработка, подождите немного.")

        text = extract_text(document.file_name)
        context.user_data["initial_prompt_txt"] = text
        for it in range(NUMBER_OF_ATTEMPTS):
            pp_text = generate_response(text)
            try:
                test_dict = text_to_dict(pp_text)
                context.user_data["feature_txt"] = pp_text
                await specify_output(update, context)
                break
            except Exception as e:
                print(f"Attempt {it + 1} failed. Error: {e}")
                print(f"Source text: {pp_text}")
        else:
            print("All attempts failed. Can't get a good answer.")
            await update.message.reply_text("Возникла непредвиденная ошибка.")
    else:
        await update.message.reply_text("Это не PDF-файл, на данный момент я работаю только с PDF.")


async def test(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = """
    {
    'Проходимость': '35 градусов',
    'Высота преодолеваемого препятствия': '100 см',
    'Тип ТС': 'Снегоболотоход',
    'Тип двигателя': 'Дизельный',
    'Мощность двигателя': 'не менее 40 л.с.',
    'Расход топлива': '3-5 л/ч',
    'Коробка передач': '5 или б-ступенчатая, механическая',
    'Длина': '3500-3880 мм',
    'Высота': '2420-2480 мм',
    'Ширина': '2500-2520 мм',
    'Клиренс': 'не менее 600 мм',
    'Скорость на суше': 'не менее 40 км/ч',
    'Скорость на воде': '6 км/ч',
    'Автономность хода': 'до 90 часов',
    'Колесная формула': '4х4',
    'Тип шин': 'Бескамерные, сверхнизкого давления',
    'Размер шин': '1600-1650 х 570-600 х 25 мм',
    'Грузоподъемность': 'до 1000 кг',
    'Буксировка': 'до 1000 кг',
    'Кабина': '2 человека',
    'Кунг, спальных мест': '2 человека',
    'Пассажировместимость': '6 человек',
    'Дополнительное оборудование': [
        'Светодиодная балка - 140 Вт',
        'Светодиодные прожекторы бокового рабочего света',
        'Светодиодные прожекторы заднего хода 40Вт',
        'Багажник с нагрузкой до 70кг',
        'Резервный АКБ',
        'Автономный отопитель кабины',
        'Автономный отопитель кунга',
        'Предпусковой подогреватель двигателя',
        'Дополнительные топливные канистры в колеса, 4шт',
        'Насос для перекачки дизельного топлива',
        'Камера заднего вида с монитором',
        'Лебедка'
    ]
}
    """
    context.user_data["initial_prompt_txt"] = data
    context.user_data["feature_txt"] = data
    await specify_output(update, context)


async def specify_output(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await delete_queries(update, context, q_type="output_queries")
    await delete_queries(update, context, q_type="name_queries")
    await delete_queries(update, context, q_type="items_queries")
    context.user_data["assistant_messages_history"] = []

    keyboard = [
        [
            InlineKeyboardButton("JSON", callback_data="json"),
            InlineKeyboardButton("Сообщение", callback_data="message"),
        ],
        [InlineKeyboardButton("Редактировать", callback_data="edit")],
        [
            InlineKeyboardButton("Сохранить", callback_data="save"),
            InlineKeyboardButton("Скрыть", callback_data="hide"),
        ],
        [InlineKeyboardButton("Рубрика эксперименты", callback_data="experiment")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    sent_message = await update.message.reply_text("Данные успешно обработаны, выберите формат вывода:",
                                                   reply_markup=reply_markup)

    context.user_data["output_queries"].append(sent_message.message_id)


async def output_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> [None, str]:
    query = update.callback_query
    await query.answer()

    pp_text = context.user_data.get("feature_txt", "{}")
    feature_dict = text_to_dict(pp_text)

    if query.data == "json":
        features_json = dict_to_json(feature_dict)
        await query.message.reply_document(document=BytesIO(features_json.encode()), filename="data.json")
    elif query.data == "message":
        text_chunks = [pp_text[i:i + MAX_MESSAGE_LENGTH] for i in range(0, len(pp_text), MAX_MESSAGE_LENGTH)]
        for text_chunk in text_chunks:
            await query.message.reply_text(text_chunk)
    elif query.data == "edit":
        await delete_queries(query, context, q_type="items_queries")
        for key, value in feature_dict.items():
            message = f"{key}: {value}"
            keyboard = [
                [
                    InlineKeyboardButton("Редактировать", callback_data="edit_item"),
                    InlineKeyboardButton("Удалить", callback_data="delete_item")
                ],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            sent_message = await query.message.reply_text(message, reply_markup=reply_markup)

            context.user_data["items_queries"].append(sent_message.message_id)
        await query.message.reply_text("Чтобы прекратить редактирование, введите /stop.")
    elif query.data == "save":
        await query.message.reply_text("Введите имя для сохранения или отмените сохранение с помощью /cancel:")
        return "AWAITING_NAME"
    elif query.data == "hide":
        await query.message.delete()


async def items_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> [None, str]:
    query = update.callback_query
    await query.answer()

    pp_text = context.user_data.get("feature_txt", "{}")
    feature_dict = text_to_dict(pp_text)
    key = parse_key(query.message.text)

    if query.data == "edit_item":
        await query.message.reply_text("Введите новое значение для фичи в формате "
                                       "key: value или отмените ввод с помощью /cancel:")
        context.user_data["temp_query"] = query
        return "AWAITING_FEATURE_EDIT"
    elif query.data == "delete_item":
        del feature_dict[key]
        context.user_data["feature_txt"] = formatted_str(feature_dict)
        await query.message.delete()


async def experimental_chatting(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    prompt = update.message.text
    if prompt != "/experiment":
        if not context.user_data.get("assistant_messages_history", []):
            context.user_data["assistant_messages_history"] = [
                {"role": "assistant", "content": context.user_data.get("feature_txt")}
            ]
        context.user_data["assistant_messages_history"].append({"role": "user", "content": prompt})

        pp_text, assistant_answer = make_direct_prompt(prompt, context.user_data.get("initial_prompt_txt"),
                                                       context.user_data.get("assistant_messages_history"))
        context.user_data["assistant_messages_history"].append({"role": "assistant", "content": assistant_answer})

        context.user_data["feature_txt"] = pp_text
        text_chunks = [pp_text[i:i + MAX_MESSAGE_LENGTH] for i in range(0, len(assistant_answer), MAX_MESSAGE_LENGTH)]
        for text_chunk in text_chunks:
            await update.message.reply_text(text_chunk)
    else:
        await update.message.reply_text("Чат-бот на связи, попробуй описать, как бы ты хотел поменять данные.")
    return "AWAITING_PROMPT"


async def handle_name_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    name = update.message.text
    feature_dict = context.user_data.get("feature_txt")
    if "saved_features" not in context.user_data:
        context.user_data["saved_features"] = {}
    context.user_data["saved_features"][name] = feature_dict
    await update.message.reply_text(f"Набор фич сохранен под именем: {name}")
    return ConversationHandler.END


async def handle_feature_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    key_new = parse_key(text)
    value = parse_value(text)

    query = context.user_data.get("temp_query")

    pp_text = context.user_data.get("feature_txt", "{}")
    feature_dict = text_to_dict(pp_text)
    key = parse_key(query.message.text)
    del feature_dict[key]

    feature_dict[key_new] = value

    keyboard = [
        [
            InlineKeyboardButton("Редактировать", callback_data="edit_item"),
            InlineKeyboardButton("Удалить", callback_data="delete_item")
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    context.user_data["feature_txt"] = formatted_str(feature_dict)
    await query.message.edit_text(f"{text}", reply_markup=reply_markup)
    await update.message.reply_text("Фича успешно отредактирована!")
    return ConversationHandler.END


async def list_of_saved_features(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await delete_queries(update, context, q_type="output_queries")
    await delete_queries(update, context, q_type="name_queries")
    await delete_queries(update, context, q_type="items_queries")

    if "saved_features" not in context.user_data:
        context.user_data["saved_features"] = {}

    keyboard = InlineKeyboardMarkup.from_column(
        [InlineKeyboardButton(name, callback_data=(name + "_features"))
         for name in context.user_data["saved_features"].keys()]
    )
    sent_message = await update.message.reply_text("Выберите сохраненные данные:", reply_markup=keyboard)

    context.user_data["name_queries"].append(sent_message.message_id)


async def choose_features_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    context.user_data["feature_txt"] = context.user_data["saved_features"][delete_postfix(query.data)]
    await specify_output(query, context)


async def compare_features_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ftext1 = context.user_data["saved_features"][context.args[0]]
    ftext2 = context.user_data["saved_features"][context.args[1]]

    comparison_results = compare_features(ftext1, ftext2)
    text_chunks = [comparison_results[i:i + MAX_MESSAGE_LENGTH]
                   for i in range(0, len(comparison_results), MAX_MESSAGE_LENGTH)]
    for text_chunk in text_chunks:
        await update.message.reply_text(text_chunk)


async def delete_queries(update: Update, context: ContextTypes.DEFAULT_TYPE, q_type: str) -> None:
    chat_id = update.message.chat.id
    messages = context.user_data.get(q_type, [])

    for message_id in messages:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception as e:
            print(f"Error deleting message {message_id}: {e}")

    context.user_data[q_type] = []


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["assistant_messages_history"] = []
    await update.message.reply_text("Ввод был отменен.")
    return ConversationHandler.END


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await delete_queries(update, context, q_type="items_queries")
    await update.message.reply_text("Редактирование отменено.")
    return ConversationHandler.END


def main() -> None:
    persistence = PicklePersistence(filepath=".hackatton_bot_data")

    application = (
        Application.builder()
        .token(TOKEN)
        .persistence(persistence)
        .arbitrary_callback_data(True)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("test", test))
    application.add_handler(CommandHandler("saved", list_of_saved_features))
    application.add_handler(CommandHandler("compare", compare_features_data))
    application.add_handler(CommandHandler("stop", stop))

    application.add_handler(CallbackQueryHandler(choose_features_data, pattern=".+_features$"))

    output_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(output_button_handler,
                                           pattern="(json|message|edit|save|hide)$")],
        states={
            "AWAITING_NAME": [MessageHandler(filters.TEXT and ~filters.COMMAND, handle_name_input)],
            "AWAITING_PROMPT": [MessageHandler(filters.TEXT and ~filters.COMMAND, experimental_chatting)]
        },
        fallbacks=[
            CommandHandler("experiment", experimental_chatting),
            CommandHandler("stop", stop),
            CommandHandler("cancel", cancel),
        ],
        allow_reentry=True,
    )
    editor_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(items_button_handler,
                                           pattern="(edit_item|delete_item)$")],
        states={"AWAITING_FEATURE_EDIT": [MessageHandler(filters.TEXT and ~filters.COMMAND, handle_feature_edit)]},
        fallbacks=[CommandHandler("stop", stop), CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    application.add_handler(output_conv_handler)
    application.add_handler(editor_conv_handler)

    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
