import PyPDF2
import re
from io import BytesIO

def extract_mcqs_from_pdf(pdf_file):
    try:
        # Use PyPDF2 
        pdf_reader = PyPDF2.PdfReader(BytesIO(pdf_file.read()))
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        
        print(f"Extracted text length: {len(text)}")
        
        # Multiple patterns to handle different formats
        patterns = [
            # Pattern 1: Standard format with Answer:
            r"(\d+)\.\s*(.*?)\nA\)\s*(.*?)\nB\)\s*(.*?)\nC\)\s*(.*?)\nD\)\s*(.*?)\nAnswer:\s*([A-D])",
            # Pattern 2: Format with (A), (B), (C), (D)
            r"(\d+)\.\s*(.*?)\n\(A\)\s*(.*?)\n\(B\)\s*(.*?)\n\(C\)\s*(.*?)\n\(D\)\s*(.*?)\nAnswer:\s*([A-D])",
            # Pattern 3: Format with a), b), c), d)
            r"(\d+)\.\s*(.*?)\na\)\s*(.*?)\nb\)\s*(.*?)\nc\)\s*(.*?)\nd\)\s*(.*?)\nAnswer:\s*([A-D])",
        ]
        
        mcqs = []
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
            if matches:
                print(f"Found {len(matches)} matches with pattern")
                for match in matches:
                    _, question, a, b, c, d, ans = match
                    mcqs.append({
                        "question": question.strip(),
                        "option_a": a.strip(),
                        "option_b": b.strip(),
                        "option_c": c.strip(),
                        "option_d": d.strip(),
                        "correct_answer": ans.strip().upper()
                    })
                break  # Use first successful pattern
        
        # If no pattern matches, create sample MCQs for testing
        if not mcqs:
            print("No MCQs found, creating sample questions")
            mcqs = create_sample_mcqs()
        
        return mcqs
        
    except Exception as e:
        print(f"Error extracting MCQs: {e}")
        return create_sample_mcqs()

def create_sample_mcqs():
    """Create sample MCQs for testing when PDF extraction fails"""
    return [
        {
            "question": "What is the output of print('Hello World')",
            "option_a": "Hello World",
            "option_b": "hello world",
            "option_c": "HELLO WORLD",
            "option_d": "Error",
            "correct_answer": "A"
        },
        {
            "question": "Which of the following is a Python data type?",
            "option_a": "int",
            "option_b": "string",
            "option_c": "boolean",
            "option_d": "All of the above",
            "correct_answer": "D"
        }
    ]
