import random
import spacy
from keybert import KeyBERT

# Load spaCy model
nlp = spacy.load("en_core_web_sm")
kw_model = KeyBERT()

def generate_mcqs(text, num_questions=5):
    """Generate MCQs from text using KeyBERT + spaCy"""
    keywords = kw_model.extract_keywords(text, keyphrase_ngram_range=(1, 2), stop_words='english', top_n=20)
    keywords = [kw[0] for kw in keywords]

    doc = nlp(text)
    sentences = [sent.text for sent in doc.sents if len(sent.text) > 20]

    mcqs = []
    for i, keyword in enumerate(keywords[:num_questions]):
        sentence = next((s for s in sentences if keyword.lower() in s.lower()), None)
        if not sentence:
            continue

        question = sentence.replace(keyword, "______", 1)
        correct_answer = keyword
        distractors = random.sample([k for k in keywords if k != keyword], k=3) if len(keywords) > 3 else ["OptionX", "OptionY", "OptionZ"]

        options = [correct_answer] + distractors
        random.shuffle(options)

        mcqs.append({
            "question": question,
            "option_a": options[0],
            "option_b": options[1],
            "option_c": options[2],
            "option_d": options[3],
            "correct_answer": chr(65 + options.index(correct_answer))
        })

    return mcqs

def normalize_ai_mcqs(ai_mcqs):
    """Normalize AI MCQs to standard format"""
    return ai_mcqs