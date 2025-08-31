import os
from fpdf import FPDF

# Directory where the text files are and where the PDFs will be saved
SOURCE_DIR = "test_emails"
FILE_NAMES = [
    "produtivo_1",
    "produtivo_2",
    "improdutivo_1",
    "improdutivo_2",
]

class PDF(FPDF):
    def header(self):
        # No header needed for this simple case
        pass
    
    def footer(self):
        # No footer needed
        pass

    def chapter_body(self, body):
        # Set font. Using a common font that supports some special characters.
        self.set_font("Arial", "", 12)
        # Add the text to the PDF. `multi_cell` handles line breaks.
        # We need to encode the text properly for fpdf.
        # The `latin-1` encoding is robust for many characters.
        self.multi_cell(0, 10, body.encode('latin-1', 'replace').decode('latin-1'))
        self.ln()

def create_pdf_from_file(file_name):
    txt_file_path = os.path.join(SOURCE_DIR, f"{file_name}.txt")
    pdf_file_path = os.path.join(SOURCE_DIR, f"{file_name}.pdf")

    try:
        with open(txt_file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Error: Could not find {txt_file_path}")
        return

    pdf = PDF()
    pdf.add_page()
    pdf.chapter_body(content)
    pdf.output(pdf_file_path)
    print(f"Successfully created {pdf_file_path}")

if __name__ == "__main__":
    # Create the directory if it doesn't exist
    if not os.path.exists(SOURCE_DIR):
        print(f"Directory '{SOURCE_DIR}' not found. Please run from the project root.")
    else:
        print("Generating PDF files...")
        for name in FILE_NAMES:
            create_pdf_from_file(name)
        print("PDF generation complete.")
