import spacy
from keybert import KeyBERT

nlp = spacy.load("en_core_web_sm")
kw_model = KeyBERT()

def extract_keywords(text, top_n=5):
    """Extract keywords using KeyBERT"""
    return [kw[0] for kw in kw_model.extract_keywords(text, top_n=top_n)]

def clean_sentences(text):
    """Split into sentences using spaCy"""
    doc = nlp(text)
    return [sent.text.strip() for sent in doc.sents if len(sent.text.strip()) > 10]
