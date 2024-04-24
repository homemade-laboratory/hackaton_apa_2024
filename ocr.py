import PyPDF2
import ocrmypdf
import os


def extract_text_from_pdf(pdf_file: str) -> str:
    with open(pdf_file, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        num_pages = len(reader.pages)
        text = ""
        for page_num in range(num_pages):
            page = reader.pages[page_num]
            text += page.extract_text()
    return text


def extract_text(f_name: str) -> str:
    dir_m = os.getcwd()
    input_path = dir_m + f"/input-pdfs/{f_name}"
    temp_path = dir_m + f"/temp/{f_name}"
    text = extract_text_from_pdf(input_path)
    if text == '':
        ocrmypdf.ocr(input_path, temp_path, language='rus')
        extracted_text = extract_text_from_pdf(temp_path)
        os.remove(temp_path)
    else:
        extracted_text = extract_text_from_pdf(input_path)
        # os.remove(input_path)
    return extracted_text


def main() -> None:
    pass


if __name__ == "__main__":
    main()
