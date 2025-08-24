import re
try:
    from nltk.stem import PorterStemmer
    from nltk.corpus import stopwords
    import nltk
    NLTK_AVAILABLE = True
except ImportError:
    NLTK_AVAILABLE = False


def stem_query(query_text):
    """
    Basic stemming for keyword search with fallback if NLTK not available
    """
    if not NLTK_AVAILABLE:
        # Simple fallback - just lowercase and basic word processing
        words = re.findall(r'\b\w+\b', query_text.lower())
        # Remove common stop words manually
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        return [word for word in words if len(word) > 2 and word not in stop_words]
    
    # Initialize NLTK components (download if needed)
    try:
        stemmer = PorterStemmer()
        stop_words = set(stopwords.words('english'))
    except Exception:
        # Download required NLTK data
        try:
            nltk.download('stopwords', quiet=True)
            stop_words = set(stopwords.words('english'))
            stemmer = PorterStemmer()
        except:
            # Fallback to simple processing
            words = re.findall(r'\b\w+\b', query_text.lower())
            stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
            return [word for word in words if len(word) > 2 and word not in stop_words]
    
    # Process query with stemming
    words = re.findall(r'\b\w+\b', query_text.lower())
    stemmed_words = []
    
    for word in words:
        if len(word) > 2 and word not in stop_words:
            stemmed_words.append(stemmer.stem(word))
    
    return stemmed_words


def expand_query_with_stems(query_text):
    """
    Expand query with stemmed variations for better keyword matching
    """
    stemmed_words = stem_query(query_text)
    
    # Add some common variations
    expanded_terms = set(stemmed_words)
    
    # Add original words too
    original_words = re.findall(r'\b\w+\b', query_text.lower())
    for word in original_words:
        if len(word) > 2:
            expanded_terms.add(word)
    
    # Add some common variations for specific terms
    variations = {
        'delus': ['delusion', 'delusional', 'delusions'],
        'think': ['thinking', 'thought', 'thoughts'],
        'ai': ['artificial intelligence', 'chatgpt', 'claude', 'llm'],
        'risk': ['danger', 'dangerous', 'risk', 'risks'],
    }
    
    for stem in stemmed_words:
        if stem in variations:
            expanded_terms.update(variations[stem])
    
    return list(expanded_terms)
