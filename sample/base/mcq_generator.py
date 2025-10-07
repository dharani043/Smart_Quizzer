import random
from .nlp_utils import extract_keywords, clean_sentences

def generate_mcqs(text, num_questions=5):
    sentences = clean_sentences(text)
    keywords = extract_keywords(text, top_n=num_questions)

    questions = []
    for i, keyword in enumerate(keywords):
        if i >= len(sentences):
            break
        q_text = sentences[i].replace(keyword, "_____")
        
        # fake options (later improve using WordNet / transformers)
        distractors = random.sample(keywords, min(3, len(keywords)))
        if keyword in distractors:
            distractors.remove(keyword)
        options = distractors[:3] + [keyword]
        random.shuffle(options)

        questions.append({
            "question": q_text,
            "options": options,
            "answer": keyword,
        })
    return questions
