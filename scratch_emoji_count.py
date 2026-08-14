import os
import re
from collections import Counter
import emoji

def extract_emojis_from_dir(directory):
    emoji_counts = Counter()
    for root, dirs, files in os.walk(directory):
        if '.git' in root or '__pycache__' in root or 'venv' in root:
            continue
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        text = f.read()
                        
                        # Extract all emojis using the emoji library
                        # Actually, emoji 2.x has emoji.emoji_list(text)
                        for em in emoji.emoji_list(text):
                            emoji_counts[em['emoji']] += 1
                except Exception as e:
                    pass
    return emoji_counts

if __name__ == '__main__':
    counts = extract_emojis_from_dir('.')
    with open("scratch_emoji_count.txt", "w", encoding="utf-8") as f:
        for em, count in counts.most_common(20):
            f.write(f"{em}: {count}\n")
