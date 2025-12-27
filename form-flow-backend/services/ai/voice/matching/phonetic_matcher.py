"""
Phonetic Matcher

Phonetic name matching for STT error tolerance.
"""

import re
from typing import List, Optional, Tuple


class PhoneticMatcher:
    """
    Match names phonetically for STT error handling.
    
    Uses Soundex-like algorithm for phonetic comparison.
    """
    
    # Sound mappings for Soundex-like algorithm
    SOUND_MAP = {
        'b': '1', 'f': '1', 'p': '1', 'v': '1',
        'c': '2', 'g': '2', 'j': '2', 'k': '2', 'q': '2', 's': '2', 'x': '2', 'z': '2',
        'd': '3', 't': '3',
        'l': '4',
        'm': '5', 'n': '5',
        'r': '6',
    }
    
    @classmethod
    def get_phonetic_key(cls, name: str) -> str:
        """
        Generate phonetic key for a name.
        
        Similar to Soundex but simplified.
        
        Args:
            name: Input name
            
        Returns:
            4-character phonetic key
        """
        if not name:
            return ""
        
        # Uppercase and get first letter
        name = name.upper()
        name = re.sub(r'[^A-Z]', '', name)  # Remove non-letters
        
        if not name:
            return ""
        
        # Keep first letter
        result = name[0]
        
        # Convert remaining letters to sounds
        prev_code = cls.SOUND_MAP.get(name[0].lower(), '0')
        
        for char in name[1:]:
            code = cls.SOUND_MAP.get(char.lower(), '0')
            if code != '0' and code != prev_code:
                result += code
            prev_code = code
        
        # Pad or truncate to 4 characters
        result = (result + '000')[:4]
        
        return result.lower()
    
    @classmethod
    def are_similar(
        cls,
        name1: str,
        name2: str,
        threshold: float = 0.8
    ) -> bool:
        """
        Check if two names are phonetically similar.
        
        Args:
            name1: First name
            name2: Second name
            threshold: Similarity threshold (0-1)
            
        Returns:
            True if names are similar
        """
        # Exact match
        if name1.lower() == name2.lower():
            return True
        
        # Phonetic key match
        k1 = cls.get_phonetic_key(name1)
        k2 = cls.get_phonetic_key(name2)
        
        if k1 == k2:
            return True
        
        # Fuzzy string match
        similarity = cls._levenshtein_similarity(name1.lower(), name2.lower())
        
        return similarity >= threshold
    
    @classmethod
    def find_best_match(
        cls,
        name: str,
        candidates: List[str],
        threshold: float = 0.7
    ) -> Optional[str]:
        """
        Find best matching name from candidates.
        
        Args:
            name: Name to match
            candidates: List of possible matches
            threshold: Minimum similarity
            
        Returns:
            Best matching name or None
        """
        if not candidates:
            return None
        
        best_match = None
        best_score = 0.0
        
        for candidate in candidates:
            score = cls._levenshtein_similarity(name.lower(), candidate.lower())
            
            # Bonus for phonetic match
            if cls.get_phonetic_key(name) == cls.get_phonetic_key(candidate):
                score = min(score + 0.15, 1.0)
            
            if score > best_score:
                best_score = score
                best_match = candidate
        
        if best_score >= threshold:
            return best_match
        
        return None
    
    @classmethod
    def _levenshtein_similarity(cls, s1: str, s2: str) -> float:
        """
        Calculate Levenshtein similarity ratio.
        
        Args:
            s1: First string
            s2: Second string
            
        Returns:
            Similarity ratio (0-1)
        """
        if not s1 and not s2:
            return 1.0
        if not s1 or not s2:
            return 0.0
        
        # Simple Levenshtein distance
        m, n = len(s1), len(s2)
        
        # Create distance matrix
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        
        for i in range(m + 1):
            dp[i][0] = i
        for j in range(n + 1):
            dp[0][j] = j
        
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if s1[i - 1] == s2[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1]
                else:
                    dp[i][j] = 1 + min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1])
        
        distance = dp[m][n]
        max_len = max(m, n)
        
        return 1 - (distance / max_len)
