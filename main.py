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
from ocr import extract_text
from post_processing import generate_response
from data_converter import text_to_dict, dict_to_json, formatted_str, create_folders
from io import BytesIO
from config import TOKEN

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 4096  # no more than 4096


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
        pp_text = generate_response(text)
        context.user_data['feature_txt'] = pp_text
        await specify_output(update, context)
    else:
        await update.message.reply_text("Это не PDF-файл, на данный момент я работаю только с PDF.")


async def test(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = """{
        'Измеряемый параметр': 'Избыточное давление',
        'Измеряемая среда': 'Нефть, вода, газ',
        'Диапазон измерения': '0-1 Мпа',
        'Возможность перенастройки верхнего предела измерения': 'Да',
        'Основная погрешность': '+/- 0,5%',
        'Температура окружающей среды': '-40 до 70°C',
        'Температура измеряемой среды': '-10 до 70°C',
        'Выходной сигнал': '4-20 мА + НАКТ',
        'Соединение с технологическим процессом': 'Наружная резьба, М20х1,5',
        'Электрическое подключение': 'Кабельный ввод, нержавеющая сталь, небронированный кабель диаметром 6,5 - 13,9 мм',
        'Исполнение по взрывозащите': 'Ex га',
        'Встроенный ЖК-индикатор': 'Да',
        'Кнопки для конфигурирования': 'Да',
        'Межповерочный интервал': '5 лет',
        'Гарантийный срок': 'Не менее 24 месяца'
    }"""
    context.user_data['feature_txt'] = data
    await specify_output(update, context)


async def specify_output(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await delete_queries(update, context, q_type="output_queries")
    await delete_queries(update, context, q_type="items_queries")
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
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    sent_message = await update.message.reply_text("Данные успешно обработаны, выберите формат вывода:",
                                                   reply_markup=reply_markup)

    if "output_queries" not in context.user_data:
        context.user_data["output_queries"] = []
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
        await delete_queries(update, context, q_type="items_queries")
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
            if "items_queries" not in context.user_data:
                context.user_data["items_queries"] = []
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
    key = query.message.text.split(":")[0]

    if query.data == "edit_item":
        await query.message.reply_text("Введите новое значение для фичи в формате "
                                       "key: value или отмените ввод с помощью /cancel:")
        context.user_data["temp_query"] = query
        return "AWAITING_FEATURE_EDIT"
    elif query.data == "delete_item":
        del feature_dict[key]
        context.user_data["feature_txt"] = formatted_str(feature_dict)
        await query.message.delete()


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
    key_new = text.split(":")[0]
    value = text.split(":")[1].strip()

    query = context.user_data.get("temp_query")

    pp_text = context.user_data.get("feature_txt", "{}")
    feature_dict = text_to_dict(pp_text)
    key = query.message.text.split(":")[0]
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


async def delete_queries(update: Update, context: ContextTypes.DEFAULT_TYPE, q_type: str) -> None:
    chat_id = update.effective_chat.id
    messages = context.user_data.get(q_type, [])

    for message_id in messages:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception as e:
            print(f"Error deleting message {message_id}: {e}")

    context.user_data[q_type] = []


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Ввод был отменен.")
    return ConversationHandler.END


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await delete_queries(update, context, q_type="items_queries")
    await update.message.reply_text("Редактирование отменено.")
    return ConversationHandler.END


def main() -> None:
    persistence = PicklePersistence(filepath="arbitrarycallbackdatabot")

    application = (
        Application.builder()
        .token(TOKEN)
        .persistence(persistence)
        .arbitrary_callback_data(True)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("test", test))
    application.add_handler(CommandHandler("stop", stop))

    output_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(output_button_handler,
                                           pattern="^(json|message|edit|save|hide)$")],
        states={"AWAITING_NAME": [MessageHandler(filters.TEXT and ~filters.COMMAND, handle_name_input)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    editor_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(items_button_handler,
                                           pattern="^(edit_item|delete_item)$")],
        states={"AWAITING_FEATURE_EDIT": [MessageHandler(filters.TEXT and ~filters.COMMAND, handle_feature_edit)]},
        fallbacks=[CommandHandler("stop", stop), CommandHandler("cancel", cancel)],
    )

    application.add_handler(output_conv_handler)
    application.add_handler(editor_conv_handler)

    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
