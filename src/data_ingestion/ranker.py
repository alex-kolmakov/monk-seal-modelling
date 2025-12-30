
from typing import List, Dict, Any

class DatasetRanker:
    def __init__(self):
        # Keywords that suggest relevance to our Monk Seal modeling
        self.priority_keywords = {
            'physics': ['current', 'velocity', 'temperature', 'salinity', 'thetao', 'uo', 'vo'],
            'biogeochemistry': ['chlorophyll', 'plankton', 'primary production', 'chl', 'npp', 'oxygen'],
            'waves': ['wave', 'swell', 'hm0', 'swh', 'vavh'], # Critical for Madeira (Storm/Cave washout risk)
            'region': ['ibi', 'atlantic', 'global'], # IBI = Iberia Biscay Ireland, covers Madeira well
            'type': ['reanalysis', 'hindcast'] # Preferred for historical modeling
        }

    def score_dataset(self, dataset: Dict[str, Any], user_tokens: List[str] = None) -> (float, List[str]):
        """
        Score a dataset based on its metadata and relevance to the user's query tokens.
        Returns a tuple of (score, list_of_reasons).
        """
        score = 0.0
        reasons = []
        title = dataset.get('title', '').lower()
        product_id = dataset.get('product_id', '').lower()
        description = dataset.get('description', '').lower()
        
        # 1. Expert Knowledge Base (Static Rules)
        
        # Region preferences
        if 'ibi' in product_id or 'ibi' in title:
            score += 5.0
            reasons.append("Covers IBI region (Madeira).")
        elif 'global' in product_id:
            score += 2.0
            reasons.append("Global coverage (includes Madeira).")
            
        # Time preferences
        if 'reanalysis' in title or 'multiyear' in title or 'my' in product_id:
            score += 3.0
            reasons.append("Reanalysis: Consistent historical data (Recommended).")
        elif 'analysis' in title or 'nrt' in product_id:
             score += 1.0
             
        # Resolution
        if '0.083deg' in title or 'high resolution' in description: 
            score += 2.0
            reasons.append("High spatial resolution.")

        # --- ECOLOGICAL INSTIGHTS INSERTION ---
        # Madeira Specific:
        # 1. Storm Risk: Waves are critical for newborn survival (wash-out).
        if any(w in title or w in product_id for w in self.priority_keywords['waves']):
            score += 4.0 # Boost wave data
            reasons.append("Wave data: Critical for modeling storm surge/pup mortality.")

        # 2. Oligotrophic Environment: Chlorophyll is needed to find the rare productive patches.
        if any(w in title or w in product_id for w in self.priority_keywords['biogeochemistry']):
           score += 3.0
           reasons.append("Biogeochemistry: Essential for prey proxy in oligotrophic waters.")
        # -------------------------------------

        # 2. Dynamic Query Relevance (User Input)
        if user_tokens:
            matched_tokens = []
            for token in user_tokens:
                token_score = 0
                if token in title:
                    token_score += 3.0
                elif token in product_id:
                    token_score += 3.0
                elif token in description:
                    token_score += 1.0
                
                if token_score > 0:
                    score += token_score
                    if token not in matched_tokens:
                        matched_tokens.append(token)
            
            if matched_tokens:
                reasons.append(f"Matches your keywords: {', '.join(matched_tokens)}.")

        return score, reasons

    def rank_datasets(self, datasets: List[Dict[str, Any]], user_query: str = "") -> List[Dict[str, Any]]:
        """
        Return datasets sorted by score.
        """
        # Simple tokenization: lowercase, split, remove small words/stopwords
        stopwords = {'the', 'a', 'an', 'in', 'on', 'at', 'for', 'to', 'of', 'and', 'is', 'are', 'model', 'modelling', 'behavior', 'behaviour', 'help', 'need', 'find', 'me', 'i'}
        raw_tokens = user_query.lower().replace('.', '').replace(',', '').split()
        user_tokens = [t for t in raw_tokens if t not in stopwords and len(t) > 2]

        scored = []
        for ds in datasets:
            s, r = self.score_dataset(ds, user_tokens)
            ds['ranking_score'] = s
            ds['ranking_reasons'] = r
            scored.append(ds)
            
        return sorted(scored, key=lambda x: x['ranking_score'], reverse=True)
